# Create a web app that tracks & records the online player count on both
#  https://colonist.io and https://steamcharts.com/app/544730 every 5 minutes.
# It should show online amount in a nice dynamic chart.


import traceback
import time
import msgpack
import requests
import websocket
from flask import Flask
from flask import jsonify
from flask import render_template

from datetime import datetime
from threading import Thread
from sqlite3worker import Sqlite3Worker

# The Sqlite3Worker passes sqlite requests through a queue
sql_worker = Sqlite3Worker("colonist.sqlite")

# ensure the table are there
sql_worker.execute("""
CREATE TABLE if not exists colonist_count (
    timestamp datetime unique not null,  
    userCountWithSocket int, 
    userCountInRooms int,
    userCountInLobby int,
    userCountInGame int,
    userCountInSpectating int ,
    gameCount int,
    roomCount int
)
""")

sql_worker.execute("""
CREATE TABLE if not exists catan_count (
    timestamp datetime unique not null,  
    userCount int
)
""")


def insert(catan_counts):
    for catan_count in catan_counts:
        [catan_time, catan_nr_user] = catan_count

        # The catan response contains all response since it started tracking, we don't need the old data.
        # We only store the datapoints since e10.7.2021
        if catan_time > 1625913801000:
            catan_date_time = datetime.fromtimestamp(catan_time / 1000)

            count = sql_worker.execute("select count(*) from catan_count c where c.timestamp = ?",
                                       (catan_date_time,))[0][0]
            if (count == 0):
                sql_worker.execute("INSERT into catan_count values (?, ?)", (catan_date_time, catan_nr_user))


def track_colonist():
    # datetime object containing current date and time
    last_insert = datetime.now()
    last_fetch_from_catan = datetime.now()
    first_fetch = True

    while True:
        try:
            # We need to first get the jwt cookie from the website
            response = requests.get("https://colonist.io")
            cookies = response.cookies.get_dict()
            header = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:88.0) Gecko/20100101 Firefox/88.0",
                      "Sec-WebSocket-Extensions": "permessage-deflate",
                      "Sec-WebSocket-Version": "13"}

            # websocket.enableTrace(True)
            print("Connect to WebSocket")
            ws = websocket.WebSocket()

            ws.connect("ws://socket.colonist.io", cookie=f"jwt={cookies['jwt']}",
                       origin="https://colonist.io", host="socket.colonist.io", header=header)

            # Send the first message so that they can start sending us data back
            ws.send_binary(msgpack.packb({"id": "1", "data": True}))

            print("Listening to messages")
            while True:
                data = msgpack.unpackb(ws.recv())

                # this is the nr-user-message
                if data['id'] == "49":

                    current_date_time = datetime.now()
                    # Ping every 5 min
                    if ((current_date_time - last_fetch_from_catan).total_seconds() > 5 * 60) or first_fetch:
                        catan_response = requests.get('https://steamcharts.com/app/544730/chart-data.json')
                        insert(catan_response.json())

                    # Store only the messages every 5min
                    if (current_date_time - last_insert).total_seconds() > 5 * 60 or first_fetch:
                        actual_data = data['data']
                        last_insert = current_date_time
                        sql_worker.execute("INSERT into colonist_count values (?, ?, ?, ?, ?, ?, ?, ?)", (
                            current_date_time,
                            actual_data['userCountWithSocket'],
                            actual_data['userCountInRooms'],
                            actual_data['userCountInLobby'],
                            actual_data['userCountInGame'],
                            actual_data['userCountInSpectating'],
                            actual_data['roomCount'],
                            actual_data['gameCount']
                        ))
                        print(data)

                    first_fetch = False
        except Exception as err:
            exception_type = type(err).__name__
            print("Failed: ", exception_type)
            print(traceback.format_exc())

            # We should delay the re-connect, in order not to force the server to block our IP (or to bombard it with
            # connection requests)
            time.sleep(10)


app = Flask(__name__)


# Service index.html on the first page
@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/user/')
def hello_world():
    result = sql_worker.execute("select * from catan_count c order by c.timestamp asc")
    colonist = sql_worker.execute("select * from colonist_count c order by c.timestamp asc")
    return jsonify({
        'catan': result,
        'colonist': colonist
    })


if __name__ == "__main__":
    # Run web socket handling in a separate thread
    thread = Thread(target=track_colonist)
    thread.start()

    app.run()

    print("Run Colonist Thread")
