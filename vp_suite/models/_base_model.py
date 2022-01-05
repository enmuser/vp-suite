import torch
import torch.nn as nn


class VideoPredictionModel(nn.Module):

    trainable = True  # most implemented models will be trainable
    can_handle_actions = False  # models by default won't be able to handle actions
    min_context_frames = 1  # models by default will be able to deal with arbitrarily many context frames

    def __init__(self, trainer_cfg, **model_args):
        super(VideoPredictionModel, self).__init__()
        if trainer_cfg is not None:
            self.img_shape = trainer_cfg["img_shape"]
            self.img_c, self.img_h, self.img_w = self.img_shape
            self.action_size = trainer_cfg["action_size"]
            self.use_actions = trainer_cfg["use_actions"]  # in that case, action_size > 0
            self.device = trainer_cfg["device"]

    @classmethod
    def model_desc(cls):
        raise NotImplementedError

    @property
    def desc(self):
        return self.__class__.model_desc()


    def forward(self, x, **kwargs):
        # input: T frames: [b, T, c, h, w]
        # output: single frame: [b, c, h, w]
        raise NotImplementedError

    def pred_n(self, x, pred_length=1, **kwargs):
        # input: T frames: [b, T, c, h, w]
        # output: pred_length (P) frames: [b, P, c, h, w]
        preds = []
        loss_dicts = []
        for i in range(pred_length):
            pred, loss_dict = self.forward(x, **kwargs)
            pred = pred.unsqueeze(dim=1)
            preds.append(pred)
            loss_dicts.append(loss_dict)
            x = torch.cat([x[:, 1:], pred], dim=1)

        pred = torch.cat(preds, dim=1)
        if loss_dicts[0] is not None:
            loss_dict = {k: torch.mean([loss_dict[k] for loss_dict in loss_dicts]) for k in loss_dicts[0]}
        else:
            loss_dict = None
        return pred, loss_dict