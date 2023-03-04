from torch.utils.data import DataLoader

from vp_suite import VPSuite

if __name__ == '__main__':
    # 1. Set up the VP Suite.
    suite = VPSuite()

    # 2. Load one of the provided datasets.
    #    They will be downloaded automatically if no downloaded data is found.
    suite.load_dataset("KTH")  # load moving MNIST dataset from default location


    # 3. Create a video prediction model.
    suite.create_model('convlstm-shi')  # create a ConvLSTM-Based Prediction Model.

    # 4. Run the training loop, optionally providing custom configuration.
    suite.train(lr=2e-4, epochs=100)
