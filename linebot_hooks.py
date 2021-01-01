from flask import request, abort, render_template
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    LineBotApiError, InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    SourceUser, SourceGroup, SourceRoom,
    TemplateSendMessage, ConfirmTemplate, MessageAction,
    ButtonsTemplate, ImageCarouselTemplate, ImageCarouselColumn, URIAction,
    PostbackAction, DatetimePickerAction,
    CameraAction, CameraRollAction, LocationAction,
    CarouselTemplate, CarouselColumn, PostbackEvent,
    StickerMessage, StickerSendMessage, LocationMessage, LocationSendMessage,
    ImageMessage, VideoMessage, AudioMessage, FileMessage,
    UnfollowEvent, FollowEvent, JoinEvent, LeaveEvent, BeaconEvent,
    MemberJoinedEvent, MemberLeftEvent,
    FlexSendMessage, BubbleContainer, ImageComponent, BoxComponent,
    TextComponent, IconComponent, ButtonComponent,
    SeparatorComponent, QuickReply, QuickReplyButton,
    ImageSendMessage)
import os

CH_ACCESS_TOKEN = os.environ['CH_ACCESS_TOKEN']
CH_SECRET = os.environ['CH_SECRET']
line_bot_api = LineBotApi(CH_ACCESS_TOKEN)
handler = WebhookHandler(CH_SECRET)


def user_text_message_handler(event):
    ''' Handler for user text message: private environment '''
    reply_text = None
    return reply_text


def room_text_message_handler(event):
    ''' Handler for room text message: protected environment '''
    reply_text = None
    return reply_text


def group_text_message_handler(event):
    ''' Handler for group text message: public environment '''
    reply_text = None
    return reply_text


@handler.add(MessageEvent, message=TextMessage)
def text_message_handler(event):
    ''' Brach to specific text message handler '''
    if isinstance(event.source, SourceUser):
        reply_text = user_text_message_handler(event)
    elif isinstance(event.source, SourceRoom):
        reply_text = room_text_message_handler(event)
    elif isinstance(event.source, SourceGroup):
        reply_text = group_text_message_handler(event)
    else:
        print('Unknown text message source')
        reply_text = None
    if reply_text is not None:
        if isinstance(reply_text, str):
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply_text)
            )
        else:
            try:
                line_bot_api.reply_message(
                    event.reply_token, reply_text
                )
            except:
                print('Unknown reply type')
                pass
