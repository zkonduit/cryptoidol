import json
import tempfile
import librosa
import numpy as np
from flask import request, jsonify, Flask
import os
from flask_cors import CORS
from pydub import AudioSegment
from mclbn256 import Fr
import api_key
import requests
import time


app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
CORS(app)


# mfcc extraction from augmented data


#extraction mel spectrogram
def extract_mel_spec(filename):
    x,sr=librosa.load(filename,duration=3,offset=0.5)
    X = librosa.feature.melspectrogram(y=x, sr=sr)
    Xdb = librosa.power_to_db(X, ref=np.max)
    Xdb = Xdb.reshape(1,128,-1)
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


@app.route('/prove', methods=['POST'])
def prove_task():
    try:
        addr = request.form['address']
        audio_file = request.files['audio'].read()

        if not addr.startswith('0x'):
            addr = '0x' + addr
        addr_ints = extract_bytes_addr(addr)

        with tempfile.NamedTemporaryFile(mode="wb+") as input_json_buffer:
            with tempfile.NamedTemporaryFile(mode="wb+") as audio_input_buffer:
                audio_input_buffer.write(audio_file)
                audio_input_buffer.flush()

                val = extract_mel_spec(audio_input_buffer.name)

                # 0 pad 2nd dim to max size
                if val.shape[2] < 130:
                    val = np.pad(
                        val, ((0, 0), (0, 0), (0, 130-val.shape[2])))
                # truncate to max size
                else:
                    val = val[:, :, :130]

                # setup input.json
                inp = {
                    "input_data": [[list(addr_ints)], val.flatten().tolist()],
                }
                inp_json_str = json.dumps(inp)
                input_json_buffer.write(inp_json_str.encode('utf-8'))

                # seek buffer to 0 before sending
                input_json_buffer.seek(0)

                print("updating artifacts with new input.json")

                headers = {
                    'X-API-KEY': api_key.API_KEY,
                    "Content-Type": "multipart/form-data"
                }

                res = requests.put(
                    url=f"{api_key.ARCHON_URL}/artifact/idol_model_2",
                    headers={"X-API-KEY": api_key.API_KEY},
                    files={
                        "data": input_json_buffer
                    }
                )

                res.raise_for_status()
                data = json.loads(res.content.decode('utf-8'))
                print(data)
                latest_uuid = data["latest_uuid"]

                # gen-witness and prove
                res = requests.post(
                    url=f"{api_key.ARCHON_URL}/spell?callback_url={api_key.CALLBACK_URL}",
                    headers={
                        "X-API-KEY": api_key.API_KEY,
                        "Content-Type": "application/json",
                    },
                    json=[
                        {
                            "ezkl_command": {
                                "GenWitness": {
                                    "data": f"input_{latest_uuid}.json",
                                    "compiled_circuit": "model.compiled",
                                    "output": f"witness_{latest_uuid}.json",
                                },
                            },
                            "working_dir": "idol_model_2",
                        },
                        {
                            "ezkl_command": {
                                "Prove": {
                                    "witness": f"witness_{latest_uuid}.json",
                                    "compiled_circuit": "model.compiled",
                                    "pk_path": "pk.key",
                                    "proof_path": f"proof_{latest_uuid}.json",
                                    # "srs_path": "k15.srs",
                                    "proof_type": "Single",
                                    "check_mode": "UNSAFE",
                                },
                            },
                            "working_dir": "idol_model_2",
                        },
                    ]
                )

                res.raise_for_status()
                data = json.loads(res.content.decode('utf-8'))
                print("full data: ", data)
                print("id: ", str(data["id"]))

                return jsonify({
                    "status": "ok",
                    "id": str(data["id"])
                })


    except Exception as e:
        return repr(e), 500


@app.route('/callback', methods=["POST"])
def callback():
    try:
        data = request.get_json()
        data_output = json.loads(data[1]['output'])
        to_save = {
            "score_hex": data_output["pretty_public_inputs"]["outputs"][1][0],
            "score": data_output["pretty_public_inputs"]["rescaled_outputs"][1][0],
            "address": data_output["pretty_public_inputs"]["outputs"][0][0],
            "proof": data_output["hex_proof"]
        }
        print(to_save)
        with open(os.path.join("proof_data", str(data[0]['spell_id'])) + ".json", "w") as f:
            json.dump(to_save, f)

        return jsonify({
            "status": "ok"
        })
    except Exception as e:
        return repr(e), 500


@app.route('/spell/<id>')
def spell(id):
    saved_file = os.path.join("proof_data", str(id) + ".json")
    if not os.path.exists(saved_file):
        return "Not Found", 400

    else:
        with open(saved_file, "r") as f:
            f = json.load(f)

         # os.remove(saved_file)

        return jsonify(f)


@app.route('/', methods=['GET'])
def index():
    return jsonify({'status': 'ok', 'res': "Welcome to ezkl proving server"})


if __name__ == '__main__':
    addr = "0x5b38da6a701c568545dcfcb03fcb875f56beddc4"
    addr_ints = extract_bytes_addr(addr)
    print("Converted {} to Addr Ints {}".format(addr, addr_ints))

    with open(os.path.join("test_files", "angry.wav"), "rb") as audio_file:
        with tempfile.NamedTemporaryFile(mode="wb+") as input_json_buffer:
            val = extract_mel_spec(audio_file)

            # 0 pad 2nd dim to max size
            if val.shape[2] < 130:
                val = np.pad(
                    val, ((0, 0), (0, 0), (0, 130-val.shape[2])))
            # truncate to max size
            else:
                val = val[:, :, :130]

            # setup input.json
            inp = {
                "input_data": [[list(addr_ints)], val.flatten().tolist()],
            }
            inp_json_str = json.dumps(inp)
            input_json_buffer.write(inp_json_str.encode('utf-8'))

            # seek buffer to 0 before sending
            input_json_buffer.seek(0)

            print("updating artifacts with new input.json")

            headers = {
                'X-API-KEY': api_key.API_KEY,
                "Content-Type": "multipart/form-data"
            }
            inp_json_str = json.dumps(inp)
            input_json_buffer.write(inp_json_str.encode('utf-8'))

            # seek buffer to 0 before sending
            input_json_buffer.seek(0)

            headers = {
                'X-API-KEY': api_key.API_KEY,
                "Content-Type": "multipart/form-data"
            }

            res = requests.put(
                url=f"{api_key.ARCHON_URL}/artifact/idol_model_2",
                headers={"X-API-KEY": api_key.API_KEY},
                files={
                    "data": input_json_buffer,
                }
            )

            res.raise_for_status()
            data = json.loads(res.content.decode('utf-8'))
            print(data)
            latest_uuid = data["latest_uuid"]

            # gen-witness and prove
            res = requests.post(
                url=f"{api_key.ARCHON_URL}/spell",
                headers={
                    "X-API-KEY": api_key.API_KEY,
                    "Content-Type": "application/json",
                },
                json=[
                    {
                        "ezkl_command": {
                            "GenWitness": {
                                "data": f"input_{latest_uuid}.json",
                                "compiled_circuit": "model.compiled",
                                "output": f"witness_{latest_uuid}.json",
                            },
                        },
                        "working_dir": "idol_model_2",
                    },
                    {
                        "ezkl_command": {
                            "Prove": {
                                "witness": f"witness_{latest_uuid}.json",
                                "compiled_circuit": "model.compiled",
                                "pk_path": "pk.key",
                                "proof_path": f"proof_{latest_uuid}.json",
                                # "srs_path": "k15.srs",
                                "proof_type": "Single",
                                "check_mode": "UNSAFE",
                            },
                        },
                        "working_dir": "idol_model_2",
                    },
                ]
            )

            res.raise_for_status()
            data = json.loads(res.content.decode('utf-8'))
            print("full data: ", data)
            print("id: ", data["id"])

            cluster_id = data["id"]


            query_count = 0
            proof_data = None

            while query_count < 60:
                time.sleep(5)
                # get job status
                # pass id to client so client polls
                res = requests.get(
                    url=f"{api_key.ARCHON_URL}/spell/{str(cluster_id)}",
                    headers={
                        "X-API-KEY": api_key.API_KEY,
                    }
                )
                res.raise_for_status()
                data = json.loads(res.content.decode('utf-8'))
                print("prove data: ", data[1])
                # print(data)
                print("prove status: ", data[1]['status'])

                status = data[1]['status']

                if status == "Complete":
                    print("COMPLETE")
                    print(data)
                    proof_data = json.loads(data[1]['output'])
                    print(proof_data)
                    break

                if status == "Errored":
                    print("ERRORED")
                    print(data)
                    break


                query_count += 1

        print(proof_data)
        print("hex_proof: ", proof_data["hex_proof"])
        print("instances: ", proof_data["pretty_public_inputs"]["outputs"])
