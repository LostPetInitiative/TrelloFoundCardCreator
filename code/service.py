import copy

import shutil
import os
import base64
import asyncio
import datetime
import base64
from time import sleep
from datetime import datetime
import requests
import json

import kafkajobs

kafkaUrl = os.environ['KAFKA_URL']
inputQueueName = os.environ['INPUT_QUEUE']
trelloKey = os.environ['TRELLO_KEY']
trelloToken = os.environ['TRELLO_TOKEN']
trelloIdList = os.environ['TRELLO_LIST']
cardStorageURL = os.environ['CARD_STORAGE_URL']
trelloAppMemberId = os.environ['TRELLO_APP_MEMBER_ID']

appName = "processedCardsTrelloCardsCreator"

worker = kafkajobs.jobqueue.JobQueueWorker(appName, kafkaBootstrapUrl=kafkaUrl, topicName=inputQueueName, appName=appName)

maxCardCreationRetryCount = 10

async def work():
    print("Service started. Pooling for a job")
    while True:        
        job = worker.GetNextJob(5000)
        uid = job["TargetID"]
        print("{0}: Starting to process the job".format(uid))
        
        splitted = uid.split("_")
        namespace = splitted[0]
        local_id = splitted[1]

        similarities = job["PossibleMatches"]
        if len(similarities) == 0:
            print(f"There are no matches. Skipping {uid}")
            worker.Commit()
            continue
        topSimilarity = similarities[0]["CosSimilarity"]
        print(f"Top similarity is {topSimilarity}")

        #query the card from storage REST API
        cardResp = requests.request(
            "GET",
            f'{cardStorageURL}/PetCards/{namespace}/{local_id}')
        if not cardResp.ok:
            print(f"Unsuccessful card fetch {uid}")
            exit(3)
        else:
            print(f"Fetched card for {uid}")
        card = cardResp.json()
        cardType = card["cardType"]

        photoResp = requests.request(
            "GET",
            f"{cardStorageURL}/PetPhotos/{namespace}/{local_id}"
        )
        if not photoResp.ok:
            print(f"Unsuccessful photos metadata fetch {uid}")
            exit(3)
        else:
            print(f"Fetched photos metadata for {uid}")
        photos = photoResp.json()
        photoCount = len(photos)
        print(f"{photoCount} photos stored for {uid}")

        if (cardType == "found") and (photoCount > 0):
            # creating a trello card
            url = "https://api.trello.com/1/cards"

            query = {
                'key': trelloKey,
                'token': trelloToken,
                'idList': trelloIdList,
                'pos': 1.0 - topSimilarity,
                'name': f"{namespace}/{local_id}:{topSimilarity:.3f}",
                'desc': f"Доступны возможные совпадения\nCosSim (CZHTTE): {topSimilarity}",
                'idMembers' : [trelloAppMemberId],
                'start': datetime.now().utcnow().isoformat()
            }

            cardCreated = False
            retryCount = 0

            while((not cardCreated) and (retryCount < maxCardCreationRetryCount)):
                response = requests.request(
                    "POST",
                    url,
                    params=query
                )

                if response.ok:
                    cardCreated = True
                    result = response.json()
                    cardID = result['id']
                    print("{0}: Successfully created Trello card. ID is {1}".format(uid, cardID))

                    # attaching image
                    # fetning image
                    photoBytesResp = requests.request(
                        "GET",
                        f"{cardStorageURL}/PetPhotos/{namespace}/{local_id}/1?preferableProcessingsStr=CalZhiruiAnnotatedHead"
                    )
                    if not photoBytesResp.ok:
                        print(f"Unsuccessful photo fetch {uid}")
                        exit(3)
                    else:
                        print(f"Fetched photo for {uid}")
        
                        url = f"https://api.trello.com/1/cards/{cardID}/attachments"
                        headers = {
                            "Accept": "application/json"
                        }
                        query = {
                            'key': trelloKey,
                            'token': trelloToken,
                            'mimeType':'image/jpeg',
                            'name': 'фото.jpg',
                            'setCover': True
                        }

                        response = requests.request(
                            "POST",
                            url,
                            files=dict(file=photoBytesResp.content),
                            headers=headers,
                            params=query
                        )
                        if response.ok:
                            print("{0}: Successfully added photo attachment Trello card. ID is {1}".format(uid, cardID))
                        else:
                            print("{0}: Error during attaching photo to Trello card; http code {1}; {2}".format(uid, response.status_code, response.text))

                    # attaching URL
                    query = {
                        'key': trelloKey,
                        'token': trelloToken,
                        'url': f"https://kashtanka.pet/#/candidatesReview/{namespace}/{local_id}"
                    }

                    response = requests.request(
                        "POST",
                        url,
                        headers=headers,
                        params=query
                        )
                    if response.ok:
                        print("{0}: Successfully added URL attachment Trello card. ID is {1}".format(uid, cardID))
                    else:
                        print("{0}: Error during attaching URL to Trello card; http code {1}; {2}".format(uid, response.status_code, response.text))
                else:
                    retryCount += 1
                    print("{0}: Error during creation of Trello card: http code {1}, {2}".format(uid,response.status_code, response.text))
            #annotatedImage = job['annotated_images'][0]
            if retryCount == maxCardCreationRetryCount:
                print("{0}: Error during creation of Trello card".format(uid))
                exit(1)
        else:
            print("{0}: Card is either not of Found type, or does not contain images".format(uid))
            
        print("{0}: Job is done. Committing".format(uid))
        worker.Commit()
        print("{0}: Commited".format(uid))

        sleep(10)
    

asyncio.run(work(),debug=False)