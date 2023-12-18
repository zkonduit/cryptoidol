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


# @celery.task
# def compute_proof(addr, audio):  # witness is a json string
#     if not addr.startswith('0x'):
#         addr = '0x' + addr
#     addr_ints = extract_bytes_addr(addr)
#     with tempfile.NamedTemporaryFile() as pffo:
#         with tempfile.NamedTemporaryFile() as wfo:
#             # write audio to temp file
#             wfo.write(audio)
#             wfo.flush()

#             val = extract_mel_spec(wfo.name)

#             # 0 pad 2nd dim to max size
#             if val.shape[2] < 130:
#                 val = np.pad(
#                     val, ((0, 0), (0, 0), (0, 130-val.shape[2])))
#             # truncate to max size
#             else:
#                 val = val[:, :, :130]

#             inp = {
#                 "input_data": [[addr_ints], val.flatten().tolist()],
#             }

#             witness = tempfile.NamedTemporaryFile()
#             audio_input = tempfile.NamedTemporaryFile(mode="w+")
#             # now save to json
#             json.dump(inp, audio_input)
#             audio_input.flush()

#             wit = ezkl.gen_witness(audio_input.name, MODEL_PATH,
#                              witness.name, settings_path=SETTINGS_PATH)

#             res = ezkl.prove(witness.name, MODEL_PATH,
#                        PK_PATH,
#                        pffo.name,
#                        SRS_PATH, 'evm', 'single', settings_path=SETTINGS_PATH)

#             # this is the quantized scord, which we convert to an int:
#             score = u64_to_fr(wit["outputs"][1][0]).__int__()

#             res = {
#                 "output_data": score,
#                 "proof": res['proof'],
#             }

#         return res


@app.route('/prove', methods=['POST'])
def prove_task():
    try:
        address = request.form['address']
        f = request.files['audio'].read()

        if not address.startswith('0x'):
            addr = '0x' + addr
        addr_ints = extract_bytes_addr(addr)

        with tempfile.NamedTemporaryFile(mode="wb+") as input_json_buffer:
            with tempfile.NamedTemporaryFile(mode="wb+") as artifact_request_buffer:
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
                    "input_data": [[addr_ints], val.flatten().tolist()],
                }
                inp_json_str = json.dumps(inp)
                input_json_buffer.write(inp_json_str.encode('utf-8'))

                # setup artifact_request
                artifact_req = {"name": "idol_model"}
                artifact_req_str = json.dumps(artifact_req)
                artifact_request_buffer.write(artifact_req_str.encode('utf-8'))

                # seek buffer to 0 before sending
                input_json_buffer.seek(0)
                artifact_request_buffer.seek(0)

                # add new input.json by updating artifact
                # TODO: this may be problematic if we have two people making requests at once
                print("updating artifacts with new input.json")

                res = requests.post(
                    url="https://archon.ezkl.xyz/artifact/update",
                    headers={"X-API-KEY": api_key.API_KEY},
                    files={
                        "artifact_request": artifact_request_buffer,
                        "data": input_json_buffer
                    }
                )

                res.raise_for_status()
                print(res.content.decode('utf-8'))

                # gen-witness and prove
                res = requests.post(
                    url="https://archon.ezkl.xyz/post-spell",
                    headers={
                        "X-API-KEY": api_key.API_KEY,
                        "Content-Type": "application/json",
                    },
                    json=[
                        {
                            "ezkl_command": {
                                "GenWitness": {
                                    "data": "input.json",
                                    "compiled_circuit": "model.compiled",
                                    "output": "witness-test.json",
                                },
                            },
                            "working_dir": "idol_model",
                        },
                        {
                            "ezkl_command": {
                                "Prove": {
                                    "witness": "witness-test.json",
                                    "compiled_circuit": "model.compiled",
                                    "pk_path": "pk.key",
                                    "proof_path": "proof.json",
                                    "srs_path": "k15.srs",
                                    "proof_type": "Single",
                                    "check_mode": "UNSAFE",
                                },
                            },
                            "working_dir": "idol_model",
                        },
                    ]
                )

                res.raise_for_status()
                data = json.loads(res.content.decode('utf-8'))
                print("full data: ", data)
                print("id: ", data["id"])

                cluster_id = data["id"]

        return jsonify({'status': 'ok', 'res': cluster_id})


    except Exception as e:
        return repr(e), 500

@app.route('/', methods=['GET'])
def index():
    return jsonify({'status': 'ok', 'res': "Welcome to ezkl proving server"})

if __name__ == '__main__':
    addr = "0x5b38da6a701c568545dcfcb03fcb875f56beddc4"
    addr_ints = extract_bytes_addr(addr)
    print("Converted {} to Addr Ints {}".format(addr, addr_ints))

    with open(os.path.join("test_files", "angry.wav"), "rb") as audio_file:
        with tempfile.NamedTemporaryFile(mode="wb+") as input_json_buffer:
            with tempfile.NamedTemporaryFile(mode="wb+") as artifact_request_buffer:
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
                    "input_data": [[addr_ints], val.flatten().tolist()],
                }
                inp_json_str = json.dumps(inp)
                input_json_buffer.write(inp_json_str.encode('utf-8'))

                # setup artifact_request
                artifact_req = {"name": "idol_model"}
                artifact_req_str = json.dumps(artifact_req)
                artifact_request_buffer.write(artifact_req_str.encode('utf-8'))

                # seek buffer to 0 before sending
                input_json_buffer.seek(0)
                artifact_request_buffer.seek(0)

                # add new input.json by updating artifact
                # TODO: this may be problematic if we have two people making requests at once
                print("updating artifacts with new input.json")

                res = requests.post(
                    url="https://archon.ezkl.xyz/artifact/update",
                    headers={"X-API-KEY": api_key.API_KEY},
                    files={
                        "artifact_request": artifact_request_buffer,
                        "data": input_json_buffer
                    }
                )

                res.raise_for_status()
                print(res.content.decode('utf-8'))

                # gen-witness and prove
                res = requests.post(
                    url="https://archon.ezkl.xyz/post-spell",
                    headers={
                        "X-API-KEY": api_key.API_KEY,
                        "Content-Type": "application/json",
                    },
                    json=[
                        {
                            "ezkl_command": {
                                "GenWitness": {
                                    "data": "input.json",
                                    "compiled_circuit": "model.compiled",
                                    "output": "witness-test.json",
                                },
                            },
                            "working_dir": "idol_model",
                        },
                        {
                            "ezkl_command": {
                                "Prove": {
                                    "witness": "witness-test.json",
                                    "compiled_circuit": "model.compiled",
                                    "pk_path": "pk.key",
                                    "proof_path": "proof.json",
                                    "srs_path": "k15.srs",
                                    "proof_type": "Single",
                                    "check_mode": "UNSAFE",
                                },
                            },
                            "working_dir": "idol_model",
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

                while query_count < 10:
                    time.sleep(3)
                    # get job status
                    # pass id to client so client polls
                    res = requests.get(
                        url=f"https://archon.ezkl.xyz/get-spell/{str(cluster_id)}",
                        headers={
                            "X-API-KEY": api_key.API_KEY,
                        }
                    )
                    res.raise_for_status()
                    data = json.loads(res.content.decode('utf-8'))
                    # print("prove data: ", data[1])
                    print("prove status: ", data[1]['status'])

                    status = data[1]['status']

                    if status == "Complete":
                        proof_data = json.loads(data[1]['output'])
                        break

                    if status == "Errored":
                        print("ERRORED")
                        print(data)
                        break


                    query_count += 1

            # print(proof_data)
            print("hex_proof: ", "0x" + proof_data["hex_proof"])
            print("instances: ", proof_data["pretty_public_inputs"]["outputs"])
