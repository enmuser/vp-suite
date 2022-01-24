from typing import TypedDict
from copy import deepcopy
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torchvision.transforms as TF
from torch.utils.data.dataset import Dataset

from vp_suite.utils.utils import set_from_kwarg


CROPS = [TF.CenterCrop, TF.RandomCrop]
SHAPE_PRESERVING_AUGMENTATIONS = [
    TF.RandomErasing, TF.Normalize, TF.RandomEqualize, TF.RandomAutocontrast, TF.RandomAdjustSharpness,
    TF.RandomSolarize, TF.RandomPosterize, TF.RandomInvert, TF.GaussianBlur, TF.RandomVerticalFlip,
    TF.RandomRotation, TF.RandomHorizontalFlip, TF.RandomGrayscale, TF.Grayscale, TF.ColorJitter,
]


class VPData(TypedDict):
    r"""TODO

    """
    frames: torch.Tensor  #: shape: [t, c, h, w]
    actions: torch.Tensor  #: shape: [t, a]


class BaseVPDataset(Dataset):
    r"""

    Attributes:

    """

    NAME: str = NotImplemented  #: the dataset's name.
    DEFAULT_DATA_DIR: Path = NotImplemented  #: the default save location of the dataset files.
    VALID_SPLITS = ["train", "test"]  #: the valid arguments for specifying splits.
    MIN_SEQ_LEN: int = NotImplemented  #: TODO
    ACTION_SIZE: int = NotImplemented  #: TODO
    DATASET_FRAME_SHAPE: (int, int, int) = NotImplemented  #: TODO

    output_frame_shape: (int, int, int) = NotImplemented  #: TODO
    train_keep_ratio: float = 0.8  #: TODO
    crop: nn.Module = None  #: TODO
    transforms: list = []  #: TODO
    split = None  #: TODO
    seq_step = 1  #: TODO
    data_dir = None  #: TODO
    value_range_min = 0.0  #: TODO
    value_range_max = 1.0  #: TODO


    def __init__(self, split, **dataset_kwargs):
        r"""

        Args:
            split ():
            **dataset_kwargs ():
        """

        super(BaseVPDataset, self).__init__()

        if split not in self.VALID_SPLITS:
            raise ValueError(f"parameter '{split}' has to be one of the following: {self.VALID_SPLITS}")
        self.split = split

        set_from_kwarg(self, "seq_step", self.seq_step, dataset_kwargs)
        self.data_dir : Path = dataset_kwargs.get("data_dir", self.data_dir)
        if self.data_dir is None:
            if not self.default_available(self.split, **dataset_kwargs):
                print(f"downloading/preparing dataset '{self.NAME}' "
                      f"and saving it to '{self.DEFAULT_DATA_DIR}'...")
                self.download_and_prepare_dataset()
            self.data_dir = self.DEFAULT_DATA_DIR

        # TRANSFORMS AND AUGMENTATIONS: crop -> resize -> augment
        crop = dataset_kwargs.get("crop", None)
        if crop is not None:
            if type(crop) not in CROPS:
                raise ValueError(f"for the parameter 'crop', only the following transforms are allowed: {CROPS}")
            self.transforms.append(crop)

        # resize (also sets output_frame_shape)
        img_size = dataset_kwargs.get("img_size", None)
        h, w, c = self.DATASET_FRAME_SHAPE
        if img_size is None:
            h_, w_ = h, w
        elif isinstance(img_size, int):
            h_, w_ = img_size, img_size
        elif (isinstance(img_size, list) or isinstance(img_size, tuple)) and len(img_size) == 2:
            h_, w_ = img_size
        else:
            raise ValueError(f"invalid img size provided, expected either None, int or a two-element list/tuple")
        self.output_frame_shape = c, h_, w_
        if h != self.output_frame_shape[1] or w != self.output_frame_shape[2]:
            self.transforms.append(TF.Resize(size=self.output_frame_shape[1:]))

        # other augmentations
        augmentations = dataset_kwargs.get("augmentations", [])
        for aug in augmentations:
            if type(aug) not in SHAPE_PRESERVING_AUGMENTATIONS:
                raise ValueError(f"within the parameter 'augmentations', "
                                 f"only the following transformations are allowed: {SHAPE_PRESERVING_AUGMENTATIONS}")
            self.transforms.append(aug)

        self.transform = nn.Sequential(*self.transforms)

        # scaling
        set_from_kwarg(self, "value_range_min", self.value_range_min, dataset_kwargs)
        set_from_kwarg(self, "value_range_max", self.value_range_max, dataset_kwargs)

        # FINALIZE
        self.ready_for_usage = False  # becomes True once sequence length has been set

    @property
    def config(self):
        r"""TODO

        Returns:

        """
        img_c, img_h, img_w = self.output_frame_shape
        base_config = {
            "name": self.NAME,
            "default_data_dir": self.DEFAULT_DATA_DIR,
            "valid_splits": self.VALID_SPLITS,
            "min_seq_len": self.MIN_SEQ_LEN,
            "action_size": self.ACTION_SIZE,
            "dataset_frame_shape": self.DATASET_FRAME_SHAPE,
            "img_shape": self.output_frame_shape,
            "img_h": img_h,
            "img_w": img_w,
            "img_c": img_c,
            "train_keep_ratio": self.train_keep_ratio,
            "transforms": self.transforms,
            "split": self.split,
            "seq_step": self.seq_step,
            "data_dir": self.data_dir,
            "value_range_min": self.value_range_min,
            "value_range_max": self.value_range_max,
            "supports_actions": self.ACTION_SIZE > 0,
        }
        return {**base_config, **self._config()}

    def _config(self):
        r"""Dataset-specific config
        """
        return {}

    def set_seq_len(self, context_frames : int, pred_frames : int, seq_step : int):
        r"""
        Set the sequence length for the upcoming run. Asserts that the given parameters
        lead to a sequence length that does not exceed the possible range.

        Args:
            context_frames ():
            pred_frames ():
            seq_step ():
        """
        total_frames = context_frames + pred_frames
        seq_len = (total_frames - 1) * seq_step + 1
        if self.MIN_SEQ_LEN < seq_len:
            raise ValueError(f"Dataset '{self.NAME}' supports videos with up to {self.MIN_SEQ_LEN} frames, "
                             f"which is exceeded by your configuration: "
                             f"{{context frames: {context_frames}, pred frames: {pred_frames}, seq step: {seq_step}}}")
        self.total_frames = total_frames
        self.seq_len = seq_len
        self.frame_offsets = range(0, (total_frames) * self.seq_step, self.seq_step)
        self._set_seq_len()
        self.ready_for_usage = True

    def _set_seq_len(self):
        r"""Optional logic for datasets with specific logic

        """
        pass

    def __len__(self) -> int:
        r"""

        Returns:

        """
        raise NotImplementedError

    def __getitem__(self, i) -> VPData:
        r"""

        Args:
            i ():

        Returns:

        """
        raise NotImplementedError

    def preprocess_img(self, x, transform=True):
        r"""

        Args:
            x ():
            transform ():

        Returns:

        """

        # conversion to torch float of range [0.0, 1.0]
        if isinstance(x, np.ndarray):
            if x.dtype == np.uint16:
                x = x.astype(np.float32) / ((1 << 16) - 1)
            elif x.dtype == np.uint8:
                x = x.astype(np.float32) / ((1 << 8) - 1)
            elif x.dtype == np.float:
                pass
            else:
                raise ValueError(f"if providing numpy arrays, only dtypes "
                                 f"np.uint8, np.float and np.uint16 are supported (given: {x.dtype})")
            x = torch.from_numpy(x)
        elif torch.is_tensor(x):
            if x.dtype == torch.uint8:
                x = x.float() / ((1 << 8) - 1)
            elif x.dtype == torch.double:
                x = x.float()
            else:
                raise ValueError(f"if providing pytorch tensors, only dtypes "
                                 f"torch.uint8, torch.float and torch.double are supported (given: {x.dtype})")
        if not torch.is_tensor(x):
            raise ValueError(f"expected input to be either a numpy array or a PyTorch tensor")

        # assuming shape = [..., h, w(, c)], putting channel dim at index -3
        if x.ndim < 2:
            raise ValueError(f"expected at least two dimensions for input image")
        elif x.ndim == 2:
            x = x.unsqueeze(dim=0)
        else:
            permutation = list(range(x.ndim - 3)) + [-1, -3, -2]
            x = x.permute(permutation)

        # scale
        if self.value_range_min != 0.0 or self.value_range_max != 1.0:
            x *= self.value_range_max - self.value_range_min  # [0, max_val - min_val]
            x += self.value_range_min  # [min_val, max_val]

        # crop -> resize -> augment
        if transform:
            x = self.transform(x)
        return x

    def postprocess_img(self, x):
        '''
        Converts a normalized tensor of an image to a denormalized numpy array.
        Input: torch.float, shape: [..., c, h, w], range (approx.): [min_val, max_val]
        Output: np.uint8, shape: [..., h, w, c], range: [0, 255]
        '''

        # assuming shape = [..., c, h, w] -> [..., h, w, c]
        if x.ndim < 3:
            raise ValueError(f"expected at least three dimensions for input image")
        else:
            permutation = list(range(x.ndim - 3)) + [-2, -1, -3]
            x = x.permute(permutation)

        x -= self.value_range_min  # ~[0, max_val - min_val]
        x /= self.value_range_max - self.value_range_min  # ~[0, 1]
        x *= 255.  # ~[0, 255]
        x = torch.clamp(x, 0., 255.)
        x = x.cpu().numpy().astype('uint8')
        return x

    def default_available(self, split, **dataset_kwargs):
        r"""
        Tries to load a dataset and a datapoint using the default data_dir value.
        If this succeeds, then we can safely use the default data dir,
        otherwise a new dataset has to be downloaded and prepared.

        Args:
            split ():
            **dataset_kwargs ():

        Returns:

        """
        try:
            kwargs_ = deepcopy(dataset_kwargs)
            kwargs_.update({"data_dir": self.DEFAULT_DATA_DIR})
            default_ = self.__class__(split, **kwargs_)
            default_.set_seq_len(1, 1, 1)
            _ = default_[0]
        except (FileNotFoundError, ValueError):  # TODO other exceptions?
            return False
        return True

    def download_and_prepare_dataset(self):
        r"""
        Downloads the specific dataset, prepares it for the video prediction task (if needed)
        and stores it in a default location in the 'data/' folder.
        Implemented by the derived dataset classes
        """
        raise NotImplementedError

    @classmethod
    def get_train_val(cls, **dataset_args):
        r"""

        Args:
            **dataset_args ():

        Returns:

        """
        if cls.VALID_SPLITS == ["train", "test"]:
            D_main = cls("train", **dataset_args)
            len_train = int(len(D_main) * cls.train_keep_ratio)
            len_val = len(D_main) - len_train
            D_train, D_val = torch.utils.data.random_split(D_main, [len_train, len_val])
        elif cls.VALID_SPLITS == ["train", "val", "test"]:
            D_train = cls("train", **dataset_args)
            D_val = cls("val", **dataset_args)
        else:
            raise ValueError(f"parameter 'VALID_SPLITS' of dataset class '{cls.__name__}' is ill-configured")
        return D_train, D_val

    @classmethod
    def get_test(cls, **dataset_args):
        r"""

        Args:
            **dataset_args ():

        Returns:

        """
        D_test = cls("test", **dataset_args)
        return D_test

    @classmethod
    def get_train_val_test(cls, **dataset_args):
        r"""

        Args:
            **dataset_args ():

        Returns:

        """
        D_train, D_val = cls.get_train_val(**dataset_args)
        D_test = cls.get_test(**dataset_args)
        return D_train, D_val, D_test