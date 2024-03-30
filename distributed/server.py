import argparse
from pydantic import BaseModel
from multiprocessing import Process, Queue
import glob
import os
import time
from PIL import Image, ImageEnhance
from multiprocessing import set_start_method
import Pyro4
import io
import base64
import pika

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
    return base64.b64encode(gif_buffer.getvalue())

def enhance_image(original_image, enhancement):
    enhanced_image = apply_enhancements(original_image, enhancement)
    img_buffer = io.BytesIO()
    enhanced_image.save(img_buffer, format='JPEG') 
    return base64.b64encode(img_buffer.getvalue())

def apply_enhancements(image, enhancement):
    brightness_enhancer = ImageEnhance.Brightness(image)
    brightness_image = brightness_enhancer.enhance(enhancement.brightness_factor)
    contrast_enhancer = ImageEnhance.Contrast(brightness_image)
    contrast_image = contrast_enhancer.enhance(enhancement.contrast_factor)
    sharpness_enhancer = ImageEnhance.Sharpness(contrast_image)
    sharpen_image = sharpness_enhancer.enhance(enhancement.sharpness_factor)
    return sharpen_image

def process_image(self, image, filename,  args):
    image = Image.open(image)
    enhancement_factors = Enhancement(
            brightness_factor=args.brightness_factor,
            contrast_factor=args.contrast_factor,
            sharpness_factor=args.sharpness_factor
            )
    if image.format=='GIF':
        enhanced = self.enhance_gif(image, enhancement_factors)
    else:
        enhanced = self.enhance_image(image, enhancement_factors) 
    message = {
        "enhanced_image": enhanced,
        "filename": filename
    } 
            
 


connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost'))

channel = connection.channel()

channel.queue_declare(queue='rpc_queue')

def fib(n):
    if n == 0:
        return 0
    elif n == 1:
        return 1
    else:
        return fib(n - 1) + fib(n - 2)

def on_request(ch, method, props, body):
    n = int(body)

    print(f" [.] fib({n})")
    response = fib(n)

    ch.basic_publish(exchange='',
                     routing_key=props.reply_to,
                     properties=pika.BasicProperties(correlation_id = \
                                                         props.correlation_id),
                     body=str(response))
    ch.basic_ack(delivery_tag=method.delivery_tag)

channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue='rpc_queue', on_message_callback=on_request)

print(" [x] Awaiting RPC requests")
channel.start_consuming()


