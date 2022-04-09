import os

def get_artifact(artifact):
    artifact_folder = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(artifact_folder, artifact)