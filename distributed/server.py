import argparse
from pydantic import BaseModel
from multiprocessing import Process, Queue
import glob
import os
import time
from PIL import Image, ImageEnhance
import io
import pika
import json
import base64

Image.MAX_IMAGE_PIXELS = None

class Enhancement(BaseModel):
    brightness_factor: int = 1
    contrast_factor: int = 1
    sharpness_factor: int = 1


def enhance_gif( original_image, enhancement):
    enhanced_frames = []
    try:
        while True:
            current_frame = original_image.copy()
            if current_frame.mode == "P":
                current_frame = current_frame.convert("RGBA")
            enhanced_frame = apply_enhancements(current_frame, enhancement)
            enhanced_frames.append(enhanced_frame)
            original_image.seek(original_image.tell() + 1)
    except EOFError:
        pass  
    gif_buffer = io.BytesIO()
    enhanced_frames[0].save(gif_buffer, save_all=True, append_images=enhanced_frames[1:], loop=0)
    gif_buffer.seek(0)
    return gif_buffer.getvalue()

def enhance_image(original_image, enhancement):
    enhanced_image = apply_enhancements(original_image, enhancement)
    img_buffer = io.BytesIO()
    enhanced_image.save(img_buffer, format='JPEG') 
    return img_buffer.getvalue()

def apply_enhancements(image, enhancement):
    brightness_enhancer = ImageEnhance.Brightness(image)
    brightness_image = brightness_enhancer.enhance(enhancement.brightness_factor)
    contrast_enhancer = ImageEnhance.Contrast(brightness_image)
    contrast_image = contrast_enhancer.enhance(enhancement.contrast_factor)
    sharpness_enhancer = ImageEnhance.Sharpness(contrast_image)
    sharpen_image = sharpness_enhancer.enhance(enhancement.sharpness_factor)
    return sharpen_image

def process_image(image, filename, args):
    image = io.BytesIO(base64.b64decode(image))
    image = Image.open(image)
    enhancement_factors = Enhancement(
            brightness_factor=args["brightness_factor"],
            contrast_factor=args["contrast_factor"],
            sharpness_factor=args["sharpness_factor"]
            )
    
    enhanced = enhance_image(image, enhancement_factors) 
    message = {
        "image": (filename, base64.b64encode(enhanced).decode('utf-8'), args)
    } 
    return message
            
 
credentials = pika.PlainCredentials("rabbituser", "rabbit1234")

connection = pika.BlockingConnection(pika.ConnectionParameters("172.17.0.1", 5672, "/", credentials))

channel = connection.channel()

channel.queue_declare(queue='rpc_queue')


def on_request(ch, method, props, body):
    body = json.loads(body)
    image_body = body["image"]
    filename = image_body[0]
    image = image_body[1]
    args = image_body[2]

    print(f" [.] Processing image {filename} ...")
    response = process_image(image, filename, args)

    ch.basic_publish(exchange='',
                     routing_key=props.reply_to,
                     properties=pika.BasicProperties(correlation_id = \
                                                         props.correlation_id),
                     body=json.dumps(response))
    ch.basic_ack(delivery_tag=method.delivery_tag)

channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue='rpc_queue', on_message_callback=on_request)

print(" [x] Awaiting RPC requests")
channel.start_consuming()

print(" [x] Awaiting RPC requests")
channel.start_consuming()


