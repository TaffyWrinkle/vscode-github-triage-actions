# ---------------------------------------------------------------------------------------------
#  Copyright (c) Microsoft Corporation. All rights reserved.
#  Licensed under the MIT License. See LICENSE in the project root for license information.
# --------------------------------------------------------------------------------------------*/

from simpletransformers.classification import ClassificationModel
import json
import os.path
import logging

BASE_PATH = os.path.join(os.path.dirname(__file__), "..")
print("running with BASE_PATH:", BASE_PATH)

logging.basicConfig(level=logging.WARN)
transformers_logger = logging.getLogger("transformers")
transformers_logger.setLevel(logging.WARN)

def make_classifier(category, config, default_target_accuracy):
    with open(os.path.join(BASE_PATH, category+'_model', 'target_names.json')) as fp:
        target_names = json.load(fp)

    with open(os.path.join(BASE_PATH, category+'_model', 'thresholds.json')) as fp:
        thresholds = json.load(fp)

    model = ClassificationModel(
        'bert',
        os.path.join(BASE_PATH, category+'_model'),
        num_labels=len(target_names),
        use_cuda=False
    )

    def classify(issue_body):
        predictions, raw_outputs = model.predict([issue_body])

        raw_output = raw_outputs[0]
        prediction_index = predictions[0]
        prediction_name = target_names[predictions[0]]
        prediction_config = config.get(prediction_name, {})

        print('got', category, prediction_name)

        target_accuracy = prediction_config.get('accuracy', default_target_accuracy)
        print('read config for ', prediction_name, 'as', prediction_config, 'setting target_accuracy', target_accuracy)

        available_accuracies = thresholds[prediction_name].keys()
        above_target_accuracies = [accuracy for accuracy in available_accuracies if float(accuracy) >= float(target_accuracy)]
        if len(above_target_accuracies) == 0:
            return {'confident': False, 'category': prediction_name, 'confidence': 0}
        target_accuracy = above_target_accuracies[0]

        print('adjusted target accuracy', target_accuracy)
        score = raw_output[prediction_index]
        threshold = thresholds[prediction_name][target_accuracy]['cutoff']
        print('score', score, 'threshold', threshold)

        confidence_estimate = max([float(accuracy)
                                for accuracy in available_accuracies
                                if float(score) >= float(thresholds[prediction_name][accuracy]['cutoff'])])

        if score < threshold:
            print('Below threshold:', prediction_name, score)
            return {'confident': False, 'category': prediction_name, 'confidence': confidence_estimate}
        else:
            print('Above threshold:', prediction_name, score)
            return {'confident': True, 'category': prediction_name, 'confidence': confidence_estimate}

    return classify


def main():
    results = []

    with open(os.path.join(BASE_PATH, "configuration.json")) as f:
        configuration = json.load(f)

    area_classifier = make_classifier('area', configuration.get('labels', {}), 0.70)
    assignee_classifier = make_classifier('assignee', configuration.get('assignees', {}), 0.75)

    with open(os.path.join(BASE_PATH, "issue_data.json")) as f:
        issue_data = json.load(f)
        for issue in issue_data:
            print("classifying", issue["number"], issue["contents"][:30].replace('\n', ' ').replace('\r', ' '))
            results.append(
                {
                    "number": issue["number"],
                    "area": area_classifier(issue["contents"]),
                    "assignee": assignee_classifier(issue["contents"]),
                    "contents": issue["contents"],
                }
            )

    print("Generated labels: ")
    for issue in results:
        print(issue["number"], ": ", "-", issue["area"], issue["assignee"])

    with open(os.path.join(BASE_PATH, "issue_labels.json"), "w") as f:
        json.dump(results, f)


if __name__ == "__main__":
    main()
