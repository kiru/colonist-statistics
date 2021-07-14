# colonist-statistics

#### What is this project?
This script connects to Colonist.io websocket and every few minutes stores the active user count in a sqlite database.

Every few minutes, the Catan server is pinged as well.

A simple HTML file plots teh collected data.


### Demo
The project is hosted on [colonist.bykiru.rocks](https://colonist.bykiru.rocks/)


#### TODO

- Reconnect WS when WebSocketConnectionClosedException is thrown

- clean data (some datapoints from catan server were 0, should not happen)


