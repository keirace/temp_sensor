from dotenv import load_dotenv
load_dotenv()
from flask import Flask
from linebot_hooks import *
from pyngrok.conf import PyngrokConfig
from pyngrok import ngrok
from threading import Thread
import paho.mqtt.client as mqtt
import numpy as np
import matplotlib.pyplot as plt
import json


app = Flask(__name__, static_url_path="/static")
app.config["TESTING"] = True
app.config["DEBUG"] = True
app.config["FLASK_ENV"] = "development"

CH_ACCESS_TOKEN = os.environ["CH_ACCESS_TOKEN"]
CH_SECRET = os.environ["CH_SECRET"]
MQTT_CLIENT_ID = os.environ['MQTT_CLIENT_ID']
MQTT_TOKEN = os.environ['MQTT_TOKEN']

line_bot_api = LineBotApi(CH_ACCESS_TOKEN)
handler = WebhookHandler(CH_SECRET)

NGROK_TOKEN = os.environ["NGROK_TOKEN"]
pyngrok_config = PyngrokConfig(region="jp")
ngrok.set_auth_token(NGROK_TOKEN)

setting = notify = graph = False
userID = client = typ = inp = None
current = max_temp = min_temp = -1
time = 60
topic = "@msg/settings"
ls = []

carousel = json.loads(open("flex.json", 'rb').read().decode('utf8'))["carousel"]
flex = json.loads(open("flex.json", 'rb').read().decode('utf8'))["notification"]

@app.route("/callback", methods=["POST"])
def callback():
    """ Main webhook for LINE """
    # get X-Line-Signature header and body
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    print("Request body: " + body)
    # handle webhook body and signature
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print(
            "Invalid signature. Please check your channel access token/channel secret."
        )
        abort(400)
    except Exception as err:
        print(err)
    return "OK"

@handler.add(FollowEvent)
def follow(event):
    profile = line_bot_api.get_profile(event.source.user_id)
    global carousel
    line_bot_api.push_message(
        event.source.user_id,
        [
            TextSendMessage("Hello, %s this is LINE TempSensor" % profile.display_name),
            StickerSendMessage(package_id="11539", sticker_id="52114131"),
            FlexSendMessage(alt_text="Options", contents=carousel)
        ]
    )
    line_bot_api.link_rich_menu_to_user('richmenu-12845d8500ffca1300a28355bd3f4580')

####################################################################################
#   Message Handler
####################################################################################

@handler.add(MessageEvent, message=TextMessage)
def message_text(event):
    if isinstance(event.source, SourceUser):
        global setting, notify, userID, ls, endpoint, graph
        msg = event.message.text
        userID = event.source.user_id
        if msg == "menus":
            global carousel
            line_bot_api.reply_message(
                event.reply_token,
                FlexSendMessage(alt_text="Menus", contents=carousel)
            )

        if msg == "temp now":
            publish(msg)
            global current
            while current == -1:
                pass
            fahrenheit = str(round(1.8*float(current) + 32, 2))
            kelvin = str(round(float(current)+273.15, 2))
            global flex
            edit_flex("Current", f"{current} °c, {fahrenheit} °f, {kelvin} K")
            line_bot_api.push_message(
                userID,
                FlexSendMessage(alt_text="Current", contents=flex)
            )
            current = -1
        if msg == "graph":
            length = json.loads(open("flex.json", 'rb').read().decode('utf8'))["length"]
            line_bot_api.reply_message(
                event.reply_token,
                FlexSendMessage("Graph duration", length)
            )
            graph = True
        if graph:
            if msg.isnumeric() and int(msg) <= 60:
                global time 
                time = int(msg)
                publish('graph')
                if len(ls) < time:
                    line_bot_api.reply_message(
                        event.reply_token, 
                        TextSendMessage(text="We are processing your temperature graph for the next period of %d seconds. Please wait..."%(time-len(ls)))
                    )
                    g = Thread(target=graph_creator, args=[True], daemon=True)
                    g.start()
                else:
                    graph_creator(False)
                    new_url = endpoint + '/static/graph.png'
                    line_bot_api.reply_message(
                        event.reply_token, 
                        ImageSendMessage(new_url, new_url)
                    )
                    graph = False
            else: 
                line_bot_api.reply_message(event.reply_token, "Graph canceled, please provide number (max:60)")
                graph=False
        if msg == "notify me" and not notify:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="Notify every how many sec?")
            )
            setting = True
            publish("yes")
            line_bot_api.link_rich_menu_to_user(event.source.user_id, "richmenu-a692a8fcd00f8db98fe111294535c762")

        elif msg == "notify me" and notify:
            global min_temp, max_temp
            publish("no")
            setting = False
            notify = False
            while min_temp == -1 or max_temp == -1:
                pass
            edit_flex("Report", f"Max: {max_temp} °c, Min: {min_temp} °c")
            line_bot_api.reply_message(
                event.reply_token,
                [
                    TextSendMessage(text="Notification canceled."),
                    FlexSendMessage(alt_text="Report", contents=flex)
                ]
            )
            min_temp, max_temp = -1, -1

        if setting and msg != 'notify me':
            if msg.isnumeric():
                sec = int(msg)
                if sec >= 1:
                    setting = False
                    notify = True
                    publish(sec)
                    line_bot_api.unlink_rich_menu_from_user(event.source.user_id)
                    # line_bot_api.link_rich_menu_to_user(event.source.user_id, "richmenu-27fcc60020636016b695d7576ab24699")
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text="Your preference has been set.")
                    )
            else:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="Canceled. Please provide number. (min:1)")
                )
                setting = False
                line_bot_api.unlink_rich_menu_from_user(event.source.user_id)
            

####################################################################################
#   Graph, Flex and Notification
####################################################################################

def graph_creator(wait):
    global ls, typ
    y_pos = [i for i in range(1, time+1)]
    while len(ls) < time:
        pass
    plt.style.use('ggplot')
    if len(ls) > time:
        new_ls = ls[60-time:60]
        plt.bar(y_pos, new_ls, color=(0.4, 0.5, 0.6, 0.6))
    else:
        plt.bar(y_pos, ls, color=(0.4, 0.5, 0.6, 0.6))
    plt.savefig("static/graph.png")
    publish('fin_graph')
    new_url = endpoint + '/static/graph.png'
    if wait:
        line_bot_api.push_message(
            userID,
            ImageSendMessage(new_url, new_url)
        )

def edit_flex(header, body):
    global flex
    flex['header']['contents'][0]['text'] = header
    flex['body']['contents'][0]['text'] = body

def notification(typ, temp):
    global notify, userID
    header = ""
    if typ == 'Max' or typ == 'Min':
        header = "New " + typ
    else: 
        header = typ
    fahrenheit = str(round(1.8*float(temp) + 32, 2))
    kelvin = str(round(float(temp)+273.15, 2))
    global flex
    edit_flex(header, f"{temp} °c, {fahrenheit} °f, {kelvin} K")
    line_bot_api.push_message(
        userID,
        FlexSendMessage(alt_text=typ, contents=flex)
    )

####################################################################################
#   MQTT
####################################################################################

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT broker!")
    else:
        print("Failed to connect with result code "+str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("@msg/tmp")

def get_message():
    global inp
    buff = str(inp.split(":")).split('\'')
    return buff[1], buff[3]

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    global ls, userID, max_temp, min_temp, typ, inp
    inp = msg.payload.decode("utf-8")
    typ, temp = get_message()
    if typ == "Current" or typ == "Temp":
        global current
        current = temp
    if notify or typ=='Rec':
        notification(typ, temp)
    if typ == 'ReportMax' or typ == 'ReportMin':
        if typ == 'ReportMax':
            max_temp = temp
        elif typ == 'ReportMin':
            min_temp = temp
    if typ == 'Temp':
        if len(ls) == time:
            ls.pop(0)
        ls.append(float(temp))
    

def publish(msg):
    result = client.publish(topic, msg)
    # result: [0, 1]
    status = result[0]
    if status == 0:
        print(f"Send `{msg}` to topic `{topic}`")
    else:
        print(f"Failed to send message to topic {topic}")

def run():
    global client
    client = mqtt.Client(MQTT_CLIENT_ID)
    client.username_pw_set(MQTT_TOKEN)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect("mqtt.netpie.io", 1883, 60)

    # Blocking call that processes network traffic, dispatches callbacks and
    # handles reconnecting.
    # Other loop*() functions are available that give a threaded interface and a
    # manual interface.
    client.loop_forever()


if __name__ == "__main__":
    global endpoint
    public_url = ngrok.connect(5001, pyngrok_config=pyngrok_config)
    endpoint = public_url.public_url
    endpoint = endpoint.replace("http://", "https://")
    print(endpoint)
    line_bot_api.set_webhook_endpoint(endpoint + "/callback")
    t = Thread(target=run)
    t.daemon = True
    t.start()
    line_bot_api.set_default_rich_menu("richmenu-12845d8500ffca1300a28355bd3f4580")
    app.run(port=5001, use_reloader=False)