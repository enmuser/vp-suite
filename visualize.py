import sys, os

import numpy as np
import torch

from config import *
from dataset import SynpickSegmentationDataset, postprocess_img, postprocess_mask, synpick_seg_val_augmentation
from utils import save_seg_vis, save_vid_vis, colorize_semseg


def visualize_seg(dataset, seg_model=None, out_dir=".", num_vis=5):

    for i in range(num_vis):
        n = np.random.choice(len(dataset))

        image, gt_mask = dataset[n]
        image_vis = postprocess_img(image.permute((1, 2, 0)))
        gt_mask_vis = postprocess_mask(gt_mask.squeeze())
        gt_mask_vis = colorize_semseg(gt_mask_vis, num_classes=dataset.num_classes)

        if seg_model is not None:
            seg_model.eval()
            with torch.no_grad():
                pr_mask = seg_model(image.to(DEVICE).unsqueeze(0))
                pr_mask_vis = postprocess_mask(pr_mask.argmax(dim=1).squeeze())
                pr_mask_vis = colorize_semseg(pr_mask_vis, num_classes=dataset.num_classes)

                save_seg_vis(
                    out_fp=os.path.join(out_dir, "{}.png".format(str(i))),
                    image=image_vis,
                    ground_truth_mask=gt_mask_vis,
                    predicted_mask=pr_mask_vis
                )
            seg_model.train()

        else:
            save_seg_vis(
                out_fp=os.path.join(out_dir, "{}.png".format(str(i))),
                image=image_vis,
                ground_truth_mask=gt_mask_vis
            )


def visualize_vid(dataset, video_in_length, video_pred_length, pred_model=None, out_dir=".",
                  vid_type=("rgb", 3), num_vis=5):

    pred_mode, num_channels = vid_type

    for i in range(num_vis):
        n = np.random.choice(len(dataset))

        data = dataset[n] # [in_l + pred_l, c, h, w]

        gt_rgb_vis = postprocess_img(data["rgb"])
        gt_colorized_vis = postprocess_img(data["colorized"])
        actions = data["actions"].to(DEVICE)

        in_traj = data[pred_mode]

        if pred_model is not None:
            pred_model.eval()
            with torch.no_grad():
                in_traj = in_traj[:video_in_length].to(DEVICE).unsqueeze(dim=0)  # [1, in_l, c, h, w]
                pr_traj, _ = pred_model.pred_n(in_traj, video_pred_length, actions=actions)  # [1, pred_l, c, h, w]
                pr_traj = torch.cat([in_traj, pr_traj], dim=1) # [1, in_l + pred_l, c, h, w]
                if num_channels == 3:
                    pr_traj_vis = postprocess_img(pr_traj.squeeze(dim=0))  # [in_l + pred_l, c, h, w]
                else:
                    pr_traj_vis = postprocess_mask(pr_traj.argmax(dim=2).squeeze())  # [in_l + pred_l, h, w]
                    pr_traj_vis = colorize_semseg(pr_traj_vis, num_classes=num_channels).transpose((0, 3, 1, 2))  # [in_l + pred_l, 3, h, w]

                save_vid_vis(
                    out_fp=os.path.join(out_dir, "{}.gif".format(str(i))),
                    video_in_length=video_in_length,
                    true_trajectory=gt_rgb_vis,
                    true_colorized=gt_colorized_vis,
                    pred_trajectory=pr_traj_vis
                )

            pred_model.train()

        else:
            save_vid_vis(
                out_fp=os.path.join(out_dir, "{}.gif".format(str(i))),
                video_in_length=video_in_length,
                true_trajectory=gt_rgb_vis,
                true_colorized=gt_colorized_vis
            )


if __name__ == '__main__':

    data_dir = sys.argv[1]
    test_img_dir = os.path.join(data_dir, 'test', 'rgb')
    test_msk_dir = os.path.join(data_dir, 'test', 'masks')
    test_dataset = SynpickSegmentationDataset(data_dir=os.path.join(data_dir, 'test'), augmentation=synpick_seg_val_augmentation())
    if len(sys.argv) > 2:
        seg_model = torch.load(sys.argv[2])
        visualize_seg(test_dataset, seg_model)
    visualize_seg(test_dataset)