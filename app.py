import json
from celery import Celery
import ezkl_lib
import tempfile
import librosa
import numpy as np
from flask import request, jsonify, Flask
import os
from flask_cors import CORS
from pydub import AudioSegment


ARTIFACTS_PATH = 'artifacts'

app = Flask(__name__)
app.config["CELERY_BROKER_URL"] = os.getenv('APP_BROKER_URI')
app.config["TEMPLATES_AUTO_RELOAD"] = True
CORS(app)

celery = Celery('worker', backend=os.getenv('APP_BACKEND'),
                broker=app.config["CELERY_BROKER_URL"])

celery.conf.update(app.config)

with open(ARTIFACTS_PATH + "/server_settings.json", 'r') as f:
    SERVER_SETTINGS = json.load(f)

MODEL_PATH = os.path.join(
    ARTIFACTS_PATH, SERVER_SETTINGS["model_path"])

SETTINGS_PATH = os.path.join(
    ARTIFACTS_PATH, SERVER_SETTINGS["settings_path"])

PK_PATH = os.path.join(
    ARTIFACTS_PATH, SERVER_SETTINGS["pk_path"])

SRS_PATH = os.path.join(
    ARTIFACTS_PATH, SERVER_SETTINGS["srs_path"])

# mfcc extraction from augmented data


def extract_stft(filename):
    # convert to wav
    audio = AudioSegment.from_file(filename)
    audio.export(filename, format='wav')
    x, sr = librosa.load(filename, duration=3, offset=0.5)
    X = librosa.stft(x)
    Xdb = librosa.amplitude_to_db(abs(X))
    Xdb = Xdb.reshape(1, 1025, -1)
    return Xdb


@celery.task
def compute_proof(audio):  # witness is a json string
    with tempfile.NamedTemporaryFile() as pffo:
        with tempfile.NamedTemporaryFile() as wfo:
            wfo.write(audio)
            wfo.flush()

            val = extract_stft(wfo.name)
            val.reshape(1, 1025, -1)

            # 0 pad 2nd dim to max size
            if val.shape[2] < 130:
                val = np.pad(
                    val, ((0, 0), (0, 0), (0, 130-val.shape[2])))
            # truncate to max size
            else:
                val = val[:, :, :130]

            inp = {
                "input_data": [val.flatten().tolist()],
            }

            witness = tempfile.NamedTemporaryFile()
            audio_input = tempfile.NamedTemporaryFile(mode="w+")
            # now save to json
            json.dump(inp, audio_input)
            audio_input.flush()

            ezkl_lib.gen_witness(audio_input.name, MODEL_PATH,
                             witness.name, settings_path=SETTINGS_PATH)

            ezkl_lib.prove(witness.name, MODEL_PATH,
                       PK_PATH,
                       pffo.name,
                       SRS_PATH, 'evm', 'single', settings_path=SETTINGS_PATH)

            # load witness output
            with open(witness.name, 'r') as witness:
                witness = json.load(witness)

            with open(SETTINGS_PATH, 'r') as settings:
                output_scale = json.load(settings)["model_output_scales"][0]

            res = {
                "output_data": witness["output_data"][0] * 2**output_scale,
                "proof": list(pffo.read()),
            }

        return res


@app.route('/prove', methods=['POST'])
def prove_task():
    try:
        f = request.files['audio'].read()
        result = compute_proof.delay(f)
        result.ready()  # returns true when ready
        res = result.get()  # bytes of proof

        return jsonify({'status': 'ok', 'res': res})

    except Exception as e:
        return e, 500


if __name__ == '__main__':
    import app
    import celery
    # read in as bytes
    inp = open('angry.wav', 'rb').read()
    result = celery.compute_proof.delay(inp)
    result.ready()  # returns true when ready
    result.get()  # bytes of proof
