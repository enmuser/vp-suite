import numpy as np
import torch
from skimage.metrics import structural_similarity as ssim
from skimage.metrics import peak_signal_noise_ratio as psnr
from skimage.metrics import mean_squared_error as mse

def SSIM(pred, target):
    # expected value range: [-1.0, 1.0]
    pred, target = pred.transpose((1, 2, 0)), target.transpose((1, 2, 0))  # color channel is needed as last dim

    # this parametrisazion matches Wang et al.: "Image quality assessment: From error visibility to structural similarity."
    return ssim(target, pred, data_range=2, win_size=5, multichannel=True,
                gaussian_weights=True, sigma=1.5, use_sample_covariance=False)

def PSNR(pred, target):
    # expected value range: [-1.0, 1.0]
    return psnr(target, pred, data_range=2)

def MSE(pred, target):
    # expected value range: [-1.0, 1.0] -> transform to [0, 255]
    pred = ((pred + 1) * 255 / 2).astype(np.uint8)
    target = ((target + 1) * 255 / 2).astype(np.uint8)
    return mse(target, pred)


def get_image_metrics(pred, target):

    if pred.shape != target.shape:
        raise ValueError("Output images and target images are of different shape!")

    # create zipper list of pred-target numpy array pairs, removing other dimensions
    pred = pred.view(-1, *pred.shape[2:])
    pred = list(pred.detach().cpu().numpy())
    target = target.view(-1, *target.shape[2:])
    target = list(target.detach().cpu().numpy())

    return {
        "ssim": np.mean(np.stack([SSIM(p, t) for p, t in zip(pred, target)]), axis=0),
        "psnr": np.mean(np.stack([PSNR(p, t) for p, t in zip(pred, target)]), axis=0),
        "mse": np.mean(np.stack([MSE(p, t) for p, t in zip(pred, target)]), axis=0),
    }

if __name__ == '__main__':

    a, b = torch.rand(8, 5, 3, 93, 124), torch.rand(8, 5, 3, 93, 124)  # [b, t, c, h, w]
    a, b = 2*a-1, 2*b-1

    for metric, val in get_image_metrics(a, a*0.95).items():
        print(f"{metric}: {val}")