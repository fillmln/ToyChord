from flask import Response, request
from flask_restful import Resource
import requests
from database import db
from utils.constants import BOOTSTRAP_NODE
from utils.common import compute_sha1_hash, bootstrap_has_joined
from models import ChordNode, KeyValuePair, NodeRecord

class Join(Resource):
    def post(self):
        # Chord node ip:port = server's ip:port.
        source_ip_port = request.host
        hashed_id = str(compute_sha1_hash(source_ip_port))

        # Ensure that this Chord node has not already joined the ring.
        if ChordNode.query.filter_by(hashed_id=hashed_id).first() is None:
            if source_ip_port != BOOTSTRAP_NODE:
                if bootstrap_has_joined():
                    # First, contact bootstrap node to get registered and obtain
                    # predecessor and successor.
                    url = "http://" + BOOTSTRAP_NODE + '/bootstrap/management'
                    bootstrap_response = requests.post(url,
                            json={'source_ip_port': source_ip_port})
                    successor = bootstrap_response.json().get('successor')
                    predecessor = bootstrap_response.json().get('predecessor')

                    # Then, save our identity in the db.
                    new_node = ChordNode(hashed_id = hashed_id,
                            successor = successor,
                            predecessor = predecessor,
                            is_bootstrap = False)
                    db.session.add(new_node)

                    # Now, communicate with our successor to inform him that we have
                    # joined and obtain our delegated data.
                    url = "http://" + successor + '/update_predecessor/' + source_ip_port
                    successor_response = requests.post(url)
                    delegated_data = successor_response.json()

                    # Save our delegated data
                    for key in delegated_data:
                        data = KeyValuePair(chordnode_id = hashed_id,
                                hashed_id = key,
                                value = delegated_data[key])
                        db.session.add(data)

                    # To finish off, communicate with our predecessor to inform him
                    # that we exist.
                    url = "http://" + predecessor + '/update_successor/' + source_ip_port
                    predecessor_responce = requests.post(url)

                    # Everything is fine, commit changes to db and leave.
                    db.session.commit()
                    response = "New node joined, with hashed id: {}, successor: {}" \
                            " and predecessor: {}".format(hashed_id, successor, predecessor)
                else:
                    response = "Bootstrap must be the first node that joins the ring!"

            # We take for granted that bootstrap node will be the first entering
            # the ring, so no data transfer has to occur.
            else:
                bootstrap_node = ChordNode(hashed_id = hashed_id,
                                           successor = BOOTSTRAP_NODE,
                                           predecessor = BOOTSTRAP_NODE,
                                           is_bootstrap = True)
                bootstrap_record = NodeRecord(bootstrap_id = 1,
                        ip_port = BOOTSTRAP_NODE)
                db.session.add(bootstrap_node)
                db.session.add(bootstrap_record)
                db.session.commit()

                response = "Bootstrap joined, with hashed id: {}".format(
                        hashed_id)
        else:
            response = "You have already joined the ring!"

        return Response(response, status=200)
