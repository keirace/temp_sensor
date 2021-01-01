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

setting = False
notify = False
userID = None
client = None
inp = None
graph = False
topic = "@msg/settings"
ls = []
max_temp = -1
min_temp = -1

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
    line_bot_api.push_message(
        event.source.user_id,
        [
            TextSendMessage("Hello, @%s this is LINE Temp Sensor" % profile.display_name),
            StickerSendMessage(package_id="11539", sticker_id="52114131")
        ]
        
    )
    line_bot_api.link_rich_menu_to_user(event.source.user_id, "richmenu-af4d07b32f2eeda666317224566eaa13")

####################################################################################
#   Message Handler
####################################################################################

@handler.add(MessageEvent, message=TextMessage)
def message_text(event):
    if isinstance(event.source, SourceUser):
        global setting, notify, userID, ls, endpoint, graph
        msg = event.message.text
        if msg == "graph":
            publish('graph')
            graph = True
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="We are processing your temperature graph for the period of 30 seconds. Please wait...")
            )
            
        if msg == "notify me" and not notify:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="Notify every how many sec?")
            )
            setting = True
            publish("yes")
            userID = event.source.user_id
            line_bot_api.link_rich_menu_to_user(event.source.user_id, "richmenu-a692a8fcd00f8db98fe111294535c762")
        elif msg == "notify me" and notify:
            line_bot_api.reply_message(
                event.reply_token,
                [
                    TextSendMessage(text="You have already turned on the temperature notification."),
                    TextSendMessage(text="To change notification time please turn off the notification first.")
                ]
            )
        if msg == "cancel" and notify:
            publish("no")
            setting = False
            notify = False
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="Notification canceled.")
            )
        elif msg == "cancel" and not notify:
            line_bot_api.reply_message(
                event.reply_token,
                    TextSendMessage(text="You have already turned off the notification.")
            )
        if setting and msg != "notify me":
            try:
                sec = int(msg)
                if sec >= 1 and sec <= 60:
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
                        TextSendMessage(text="Please provide number between 1-60.")
                    )
            except:
                print("in exception")
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="Please provide number between 1-60.")
                    )
    
def notification(typ, temp):
    global notify, userID
    fahrenheit = 1.8*float(temp) + 32
    kelvin = float(temp)+273.15
    line_bot_api.push_message(
            userID,
            TextSendMessage(f"{typ} : \n{temp} °c\n{round(fahrenheit, 2)} °f\n{round(kelvin, 2)} K")
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
    buff = str(inp.split(":")).split('\'')
    return buff[1], buff[3]

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    global inp, graph, ls, userID, max_temp, min_temp
    inp = msg.payload.decode("utf-8")
    typ, temp = get_message()
    if notify:
        notification(typ, temp)
    if graph:
        y_pos = [i for i in range(1, 31)]
        if typ == 'Temp' and len(ls) < 30:
            ls.append(temp)
        if len(ls) == 30:
            plt.bar(y_pos, ls, color=(0.2, 0.4, 0.6, 0.6))
            plt.savefig("static/graph.png")
            ls = []
            publish('fin_graph')
            new_url = endpoint + '/static/graph.png'
            line_bot_api.push_message(
                userID,
                ImageSendMessage(new_url, new_url)
            )
            graph = False
    if typ == 'ReportMax' or typ == 'ReportMin':
        if typ == 'ReportMax':
            max_temp = temp
        elif typ == 'ReportMin':
            min_temp = temp
        if min_temp != -1 and max_temp != -1:
            line_bot_api.push_message(
                userID,
                TextSendMessage(text=f"Report:\nMax: {max_temp}°c, Min: {min_temp}°c")
            )
            min_temp, max_temp = -1, -1

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
    # m5.run()
    t = Thread(target=run)
    t.daemon = True
    t.start()
    line_bot_api.set_default_rich_menu("richmenu-af4d07b32f2eeda666317224566eaa13")
    app.run(port=5001, use_reloader=False)