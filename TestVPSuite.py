from vp_suite import VPSuite

# 1. Set up the VP Suite.
suite = VPSuite()

# 2. Load one of the provided datasets in test mode.
#    They will be downloaded automatically if no downloaded data is found.
suite.load_dataset("MM", split="test")  # load moving MNIST dataset from default location

# 3. Get the filepaths to the models you'd like to test and load the models
model_dirs = ["out/model_foo/", "out/model_bar/"]
for model_dir in model_dirs:
    suite.load_model(model_dir, ckpt_name="best_model.pth")

# 4. Test the loaded models on the loaded test sets.
suite.test(context_frames=5, pred_frames=10)