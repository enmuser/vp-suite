from vp_suite import VPSuite

from sys import platform


# 'copy': CopyLastFrame
# 'lstm': NonConvLSTM
# 'unet-3d': UNet-3D
# 'phy': PhyDNet
# 'st-phy': ST-Phy
# 'convlstm-shi': EF-ConvLSTM (Shi et al.)
# 'trajgru': EF-TrajGRU (Shi et al.)
# 'predrnn-pp': PredRNN++
# None
# -----------------------------------------
# 'MM': Moving MNIST
# 'MMF': Moving MNIST - On the fly
# 'BAIR': BAIR robot pushing
# 'KTH': KTH Actions
# 'SPM': SynPick - Moving
# 'P101': Physics 101
# 'H36M': Human 3.6M
# 'KITTI': KITTI raw
# 'CP': Caltech Pedestrian
# None


print(VPSuite().list_available_models())
print("-----------------------------------------")
print(VPSuite().list_available_datasets())