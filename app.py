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
from mclbn256 import Fr

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
    Xdb = abs(X)
    Xdb = Xdb.reshape(1, 1025, -1)
    return Xdb

def extract_bytes_addr(addr): 
    addr_int = int(addr, 0)
    rep = Fr(addr_int)

    ser = rep.serialize()

    first_byte = int.from_bytes(ser[0:8], "little")
    second_byte = int.from_bytes(ser[8:16], "little")
    third_byte = int.from_bytes(ser[16:24], "little")
    fourth_byte = int.from_bytes(ser[24:32], "little")

    return [first_byte, second_byte, third_byte, fourth_byte]

def u64_to_fr(array):
    reconstructed_bytes = array[0].to_bytes(8, byteorder='little') \
                            + array[1].to_bytes(8, byteorder='little') \
                              + array[2].to_bytes(8, byteorder='little') \
                                + array[3].to_bytes(8, byteorder='little')
    return Fr(reconstructed_bytes)


@celery.task
def compute_proof(addr, audio):  # witness is a json string
    if not addr.startswith('0x'):
        addr = '0x' + addr
    addr_ints = extract_bytes_addr(addr)
    with tempfile.NamedTemporaryFile() as pffo:
        with tempfile.NamedTemporaryFile() as wfo:
            # write audio to temp file
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
                "input_data": [[addr_ints], val.flatten().tolist()],
            }

            witness = tempfile.NamedTemporaryFile()
            audio_input = tempfile.NamedTemporaryFile(mode="w+")
            # now save to json
            json.dump(inp, audio_input)
            audio_input.flush()

            wit = ezkl_lib.gen_witness(audio_input.name, MODEL_PATH,
                             witness.name, settings_path=SETTINGS_PATH)

            res = ezkl_lib.prove(witness.name, MODEL_PATH,
                       PK_PATH,
                       pffo.name,
                       SRS_PATH, 'evm', 'single', settings_path=SETTINGS_PATH)

            # this is the quantized scord, which we convert to an int:
            score = u64_to_fr(wit["output_data"][1][0]).__int__()

            res = {
                "output_data": score,
                "proof": res['proof'],
            }

        return res


@app.route('/prove', methods=['POST'])
def prove_task():
    try:
        address = request.form['address']
        f = request.files['audio'].read()
        result = compute_proof.delay(address, f)
        result.ready()  # returns true when ready
        res = result.get()  # bytes of proof

        return jsonify({'status': 'ok', 'res': res})

    except Exception as e:
        return repr(e), 500

@app.route('/', methods=['GET'])
def index():
    return jsonify({'status': 'ok', 'res': "Welcome to ezkl proving server"})

if __name__ == '__main__':
    addr = "0xb794f5ea0ba39494ce839613fffba74279579268"
    addr_int = int(addr, 0)
    rep = Fr(addr_int)
    print(rep)

    ser = rep.serialize()

    first_byte = int.from_bytes(ser[0:8], "little")
    second_byte = int.from_bytes(ser[8:16], "little")
    third_byte = int.from_bytes(ser[16:24], "little")
    fourth_byte = int.from_bytes(ser[24:32], "little")


    print(first_byte)
    print(second_byte)
    print(third_byte)
    print(fourth_byte)

    reconstructed_bytes = first_byte.to_bytes(8, byteorder='little') + second_byte.to_bytes(8, byteorder='little') + third_byte.to_bytes(8, byteorder='little') + fourth_byte.to_bytes(8, byteorder='little')

    recon = Fr.deserialize(reconstructed_bytes)

    assert rep == recon




