import argparse
import glob
import os

import numpy as np
import torch
from sklearn.metrics import accuracy_score

import models_torch as models
import utils


EXPERIMENT_DATA_DIR = "/tmp/mgr"


def inference(parameters, verbose=True) -> int:

    # resolve device
    device = torch.device(
        "cuda:{}".format(parameters["gpu_number"]) if parameters["device_type"] == "gpu"
        else "cpu"
    )

    # load input images
    datum_l_cc = utils.load_images(parameters['image_path'], 'L-CC')
    datum_r_cc = utils.load_images(parameters['image_path'], 'R-CC')
    datum_l_mlo = utils.load_images(parameters['image_path'], 'L-MLO')
    datum_r_mlo = utils.load_images(parameters['image_path'], 'R-MLO')

    # construct models and prepare data
    if parameters["model_type"] == 'cnn':
        model = models.BaselineBreastModel(device, nodropout_probability=1.0, gaussian_noise_std=0.0).to(device)
        model.load_state_dict(torch.load(parameters["model_path"]))
        x = {
            "L-CC": torch.Tensor(datum_l_cc).permute(0, 3, 1, 2).to(device),
            "L-MLO": torch.Tensor(datum_l_mlo).permute(0, 3, 1, 2).to(device),
            "R-CC": torch.Tensor(datum_r_cc).permute(0, 3, 1, 2).to(device),
            "R-MLO": torch.Tensor(datum_r_mlo).permute(0, 3, 1, 2).to(device),
        }
    elif parameters["model_type"] == 'histogram':
        model = models.BaselineHistogramModel(num_bins=parameters["bins_histogram"]).to(device)
        model.load_state_dict(torch.load(parameters["model_path"]))
        x = torch.Tensor(utils.histogram_features_generator([
            datum_l_cc, datum_r_cc, datum_l_mlo, datum_r_mlo
        ], parameters)).to(device)
    else:
        raise RuntimeError(parameters["model_type"])

    # run prediction
    with torch.no_grad():
        prediction_density = model(x).cpu().numpy()

    if verbose:
        # nicely prints out the predictions
        print('Density prediction:\n'
              '\tAlmost entirely fatty (0):\t\t\t' + str(prediction_density[0, 0]) + '\n'
              '\tScattered areas of fibroglandular density (1):\t' + str(prediction_density[0, 1]) + '\n'
              '\tHeterogeneously dense (2):\t\t\t' + str(prediction_density[0, 2]) + '\n'
              '\tExtremely dense (3):\t\t\t\t' + str(prediction_density[0, 3]) + '\n')

    return np.argmax(prediction_density[0])+1 # return density in scope 1 to 4


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Run Inference')
    parser.add_argument('model_type')
    parser.add_argument('--bins-histogram', default=50)
    parser.add_argument('--model-path', default=None)
    parser.add_argument('--device-type', default="cpu")
    # parser.add_argument('--image-path', default="images/")
    args = parser.parse_args()

    parameters_ = {
        "model_type": args.model_type,
        "bins_histogram": args.bins_histogram,
        "model_path": args.model_path,
        "device_type": args.device_type,
        # "image_path": args.image_path,
    }

    if parameters_["model_path"] is None:
        if args.model_type == "histogram":
            parameters_["model_path"] = "saved_models/BreastDensity_BaselineHistogramModel/model.p"
        if args.model_type == "cnn":
            parameters_["model_path"] = "saved_models/BreastDensity_BaselineBreastModel/model.p"

    predicted_values = []
    real_values = []

    predicted_values_two_classes = []
    real_values_two_classes = []

    two_classes_mapping = {1: 0, 2: 0, 3: 1, 4: 1}

    for dir in glob.glob(f"{EXPERIMENT_DATA_DIR}/*/"):
        parameters_["image_path"] = dir
        predicted_density = inference(parameters_)

        with open(os.path.join(dir, "density.txt")) as file:
            real_density = int(file.read())
        print(f"Predicted density: {predicted_density}")
        print(f"Real density: {real_density}\n")

        print(f"Predicted density (2 cls): {two_classes_mapping[predicted_density]}")
        print(f"Real density (2 cls): {two_classes_mapping[real_density]}\n")

        predicted_values.append(predicted_density)
        real_values.append(real_density)

        predicted_values_two_classes.append(two_classes_mapping[predicted_density])
        real_values_two_classes.append(two_classes_mapping[real_density])

    print(f"Total accuracy: {accuracy_score(real_values, predicted_values)}")
    print(f"Total accuracy two classes: {accuracy_score(real_values_two_classes, predicted_values_two_classes)}")


"""
python density_model_torch_custom.py histogram
python density_model_torch_custom.py cnn
"""
