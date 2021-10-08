import os, json, time

import numpy as np
import torch
import torch.nn.functional as F
from scipy.spatial.transform import Rotation as R
from dual_quaternions import DualQuaternion

import networkx as nx
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

from torch_geometric.data import Data as GraphData
from torch_geometric.utils.convert import to_networkx
from torch_geometric_temporal.signal import DynamicGraphTemporalSignal


class SynpickGraphDataset(object):
    def __init__(self, data_dir, num_frames, step, allow_overlap):
        super(SynpickGraphDataset, self).__init__()

        scene_dir = os.path.join(data_dir, 'scene_gt')
        self.scene_ids = {int(scene_fp[-20:-14]): os.path.join(scene_dir, scene_fp)
                          for scene_fp in sorted(os.listdir(scene_dir))}

        self.skip_first_n = 72
        self.step = step  # if >1, (step - 1) frames are skipped between each frame
        self.sequence_length = (num_frames - 1) * self.step + 1  # num_frames also includes prediction horizon
        self.frame_offsets = range(0, num_frames * self.step, self.step)

        # Frames are packed like [[x_0, x_1, x_2, ...], [x_1, x_2, x_3...], ...] if overlap is allowed.
        # Otherwise, [[x_0, x_1, x_2, ...], [x_3, x_4, x_5, ...], ...]
        self.allow_overlap = allow_overlap
        self.action_size = 3

        # determine which dataset indices are valid for given sequence length T
        self.n_total_frames = 0
        self.valid_frames = []
        for ep, scene_fp in self.scene_ids.items():
            ep = int(scene_fp[-20:-14])
            with open(scene_fp, "r") as scene_json_file:
                scene_dict = json.load(scene_json_file)

            # discard episode if it includes objects that fell out of the bin (-> obj. height exceeds max_height)
            ep_obj_pos = [obj_dict["cam_t_m2c"] for frame_list in scene_dict.values() for obj_dict in frame_list]
            if any([outside_tote(pos) for pos in ep_obj_pos]):
                print(f"skipping episode {ep} because an object is outside the tote")
                continue

            frames = sorted([int(frame_str) for frame_str in scene_dict.keys()])
            self.n_total_frames += len(frames)
            next_available_idx = 0
            for i in range(self.skip_first_n, len(frames)):

                start_frame = frames[i]
                # discard start_frame if starting from current start_frame would cause overlap
                if start_frame < next_available_idx:
                    continue

                sequence_frames = [start_frame + offset for offset in self.frame_offsets]
                # discard episode if sequences_frames reaches end of episode
                if sequence_frames[-1] > frames[-1]:
                    break

                # all conditions are met -> add start_frame to list of valid sequence_dps and move on
                self.valid_frames.append((ep, start_frame))
                if self.allow_overlap:
                    next_available_idx = start_frame + 1
                else:
                    next_available_idx = start_frame + self.sequence_length

        if len(self.valid_frames) < 1:
            raise ValueError("No valid indices in generated dataset! "
                             "Perhaps the calculated sequence length is longer than the trajectories of the data?")


    def __getitem__(self, i):

        ep, start_frame = self.valid_frames[i]  # only consider valid indices
        frame_list = self.get_scene_frames(ep, start_frame)  # list of lists of object information dicts

        gripper_pos = np.array([frame_info[-1]["cam_t_m2c"] for frame_info in frame_list])
        gripper_pos_deltas = np.stack([new - old for old, new in zip(gripper_pos, gripper_pos[1:])], axis=0)
        gripper_actions = F.pad(torch.from_numpy(gripper_pos_deltas), (0, 0, 0, 1))  # last graph gets padded action

        edge_indices, edge_weights, node_features, targets = [], [], [], []
        for frame_info, action in zip(frame_list, gripper_actions):
            all_instance_ids = [obj_info["ins_id"] for obj_info in frame_info]
            edge_indices_t, node_features_t = [], []
            for obj_info in frame_info:

                # assemble node feature vector
                rotmat = obj_info["cam_R_m2c"]
                r_q = R.from_matrix([rotmat[i:i+3] for i in [0, 3, 6]]).as_quat()  # rotation in quaternions
                t_vec = normalize_t(obj_info["cam_t_m2c"])
                pose_dq = DualQuaternion.from_quat_pose_array(np.concatenate([r_q, t_vec]))
                obj_feature = np.array(pose_dq.dq_array() ++ [obj_info["obj_id"]])  # object's feature (x) vector
                node_features_t.append(obj_feature)

                # assemble outgoing edges
                instance_idx = obj_info["ins_id"]  # object's instance idx
                node_idx = all_instance_ids.index(instance_idx)
                touches = obj_info.get("touches", [idx for idx in all_instance_ids if idx != instance_idx])  # list of instance idx this object touches
                touched_node_idx = [all_instance_ids.index(t) for t in touches]
                edge_indices_t.extend([np.array([node_idx, touch_idx]) for touch_idx in touched_node_idx])

            node_features.append(np.stack(node_features_t, axis=0))  # shape: [|V|, feat_dim]
            edge_indices_t = np.stack(edge_indices_t, axis=1)
            edge_indices.append(edge_indices_t)  # shape: [2, |E|]
            edge_weights.append(np.ones(edge_indices_t.shape[1]))  # shape: [|E|]
            targets.append(None)
            # TODO actions as global features

        # sequence consists of T graphs with the labels being the features from the following graph
        return DynamicGraphTemporalSignal(
            edge_indices = edge_indices,
            edge_weights = edge_weights,
            features = node_features,
            targets = targets
        )

    def get_dataset(self):
        return self.__getitem__(0)



    def __len__(self):
        return len(self.valid_frames)


    def get_scene_frames(self, ep : int, start_frame : int):
        '''
        This function assumes that all given ep-frame combinations exist!
        '''
        with open(self.scene_ids[ep], "r") as scene_json_file:
            ep_dict = json.load(scene_json_file)
        sequence_frames = [start_frame + offset for offset in self.frame_offsets]
        return [ep_dict[str(frame)] for frame in sequence_frames]


tote_min_coord = [-300, -200, 1500]
tote_max_coord = [ 300,  200, 2000]

def outside_tote(pos):
    return pos[0] < tote_min_coord[0]\
           or pos[1] < tote_min_coord[1]\
           or pos[2] < tote_min_coord[2]\
           or pos[0] > tote_max_coord[0]\
           or pos[1] > tote_max_coord[1]\
           or pos[2] > tote_max_coord[2]

def normalize_t(pos):
    return 2 * np.divide(np.array(pos) - tote_min_coord, np.array(tote_max_coord) - tote_min_coord) - 1

def denormalize_t(pos):
    pos_dim = pos.shape[1]
    max_c = tote_max_coord[0:pos_dim]
    min_c = tote_min_coord[0:pos_dim]
    return ((np.array(pos) + 1) / 2) * (np.array(max_c) - min_c) + min_c


def draw_synpick_pred_and_gt(graph_pred, graph_target, out_fp, frame=0):

    graph_pred_dict = graph_pred.to_dict()
    graph_pred_dict.update({"obj_class": graph_pred_dict["x"][:, 7]})
    graph_target_dict = graph_target.to_dict()
    graph_target_dict.update({"obj_class": graph_target_dict["x"][:, 7]})

    y_pred = graph_pred_dict["x"].cpu().numpy()[:, 4:7]
    y_target = graph_target_dict["x"].cpu().numpy()[:, 4:7]
    G_pred = to_networkx(GraphData.from_dict({**graph_pred_dict, "pos": denormalize_t(y_pred)}),
                         to_undirected=True, node_attrs=["pos", "obj_class"], edge_attrs=["edge_attr"])
    G_target = to_networkx(GraphData.from_dict({**graph_target_dict, "pos": denormalize_t(y_target)}),
                           to_undirected=True, node_attrs=["pos", "obj_class"], edge_attrs=["edge_attr"])

    # create plot and save
    fig = plt.figure(figsize=(10, 10))
    ax = Axes3D(fig)
    network_plot_3D(ax, G_pred, alpha=1.0, angle=1*frame)
    network_plot_3D(ax, G_target, alpha=0.25, angle=1*frame, out_fp=out_fp)


def network_plot_3D(ax, G, alpha, angle=0, out_fp=None):

    ROT_AX_LEN = 10

    pos = nx.get_node_attributes(G, 'pos')
    n = G.number_of_nodes()
    node_cmap = plt.cm.get_cmap("gist_ncar")
    node_colors = [node_cmap(G.nodes[i]["obj_class"] / 24) for i in range(n)]
    edge_alphas = [min(w, 1.0) for _, _, w in G.edges.data("edge_attr")]

    # Loop on the pos dictionary to extract the x,y,z coordinates of each node
    for key, value in pos.items():
        xi, yi, zi = value
        ax.scatter(xi, yi, zi, s=100, color=node_colors[key], edgecolors="face", alpha=alpha)
        ax.plot(np.array((xi, xi+ROT_AX_LEN)), np.array((yi, yi)), np.array((zi, zi)), c="r", alpha=alpha, linewidth=2)  # rot_ax_x
        ax.plot(np.array((xi, xi)), np.array((yi, yi+ROT_AX_LEN)), np.array((zi, zi)), c="g", alpha=alpha, linewidth=2)  # rot_ax_y
        ax.plot(np.array((xi, xi)), np.array((yi, yi)), np.array((zi, zi+ROT_AX_LEN)), c="b", alpha=alpha, linewidth=2)  # rot_ax_z

    # Loop on the list of edges to get the x,y,z, coordinates of the connected nodes
    # Those two points are the extrema of the line to be plotted
    for i, j in enumerate(G.edges()):
        x = np.array((pos[j[0]][0], pos[j[1]][0]))
        y = np.array((pos[j[0]][1], pos[j[1]][1]))
        z = np.array((pos[j[0]][2], pos[j[1]][2]))

        # Plot the connecting lines
        ax.plot(x, y, z, c='black', alpha=edge_alphas[key]*alpha, linewidth=0.5)

    # Set the initial view
    ax.view_init(20, angle)
    ax.set_xlim(tote_min_coord[0], tote_max_coord[0]);
    ax.set_ylim(tote_min_coord[1], tote_max_coord[1]);
    ax.set_zlim(1800, 2000);

    if out_fp is not None:
        plt.savefig(out_fp)
        plt.close('all')

    return