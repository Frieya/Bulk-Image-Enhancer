import argparse
from multiprocessing import Process, Queue
import glob
import os
import time
from PIL import Image, ImageEnhance
from multiprocessing import set_start_method
import pika
import uuid
from io import BytesIO
import json
import base64
Image.MAX_IMAGE_PIXELS = None


class ImageEnhanceRpcClient(object):
    def __init__(self):
        self.credentials = pika.PlainCredentials("rabbituser", "rabbit1234")

        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host="10.2.201.128", port=5672, virtual_host="/", credentials=self.credentials))

        self.channel = self.connection.channel()

        result = self.channel.queue_declare(queue='', exclusive=True)
        self.callback_queue = result.method.queue

        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response,
            auto_ack=True)

        self.response = None
        self.corr_id = None

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body

    def call(self, message):
        self.response = None
        self.corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange='',
            routing_key='rpc_queue',
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ),
            body=json.dumps(message))
        while self.response is None:
            self.connection.process_data_events(time_limit=None)
        return self.response
    
class BulkImageEnhancer():
    def __init__(self, args) -> None:
        self.args = {
            "brightness_factor":args.brightness_factor,
            "contrast_factor":args.contrast_factor,
            "sharpness_factor":args.sharpness_factor
        }
        self.input_dir = os.path.join(os.getcwd(), args.input_dir)
        self.output_dir =os.path.join(os.getcwd(), args.output_dir)
        assert os.path.exists(self.input_dir)
        self.createFolderIfNotExist()
        self.image_buffer = Queue()
        self.image_count = 0
        self.get_image_dir()

    def createFolderIfNotExist(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def get_image_dir(self):
        png_image_list = glob.glob(os.path.join(self.input_dir, '*.png'))
        jpg_image_list = glob.glob(os.path.join(self.input_dir, '*.jpg'))
        gif_image_list = glob.glob(os.path.join(self.input_dir, '*.gif'))
        image_list = [*png_image_list, *jpg_image_list, *gif_image_list]
        self.image_count = len(image_list)
        list(map(self.image_buffer.put, image_list))
    
    def run_image_enhancer(self, process_num):
        while True:
            if self.image_buffer.empty():
                break
            image_path = self.image_buffer.get()
            image_enhance_rpc = ImageEnhanceRpcClient()
            image_name = os.path.basename(image_path)
            output_path = os.path.join(self.output_dir, f"enhanced_{image_name}")
            print(f" [x] Requesting server to enhance image {image_name}")
            with open(image_path, "rb") as image:
                image_byte = image.read()
            message = {'image': (image_name, base64.b64encode(image_byte).decode('utf-8'), self.args)}
            response = image_enhance_rpc.call(message)
            response = json.loads(response)
            with open(output_path, "wb") as enhanced_image:
                enhanced_image.write(base64.b64decode(response["image"][1]))
            print(f" [.] Got {response['image'][0]}")
        return True
    
    def __repr__(self) -> str:
        return f"BulkImageEnhancer processed {self.image_count} images, saved in {self.output_dir}\n"

    


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input_dir', dest='input_dir', default="./input_dir")
    parser.add_argument('--output_dir', dest='output_dir', default="./output_dir")
    parser.add_argument('--brightness_factor', dest='brightness_factor', default=1)
    parser.add_argument('--sharpness_factor', dest='sharpness_factor', default=1)
    parser.add_argument('--contrast_factor', dest='contrast_factor', default=1)
    parser.add_argument('--num_threads', dest='num_threads', default=1)
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    args = parse_args()
    bulk_enhancer = BulkImageEnhancer(args)
    enhancer_process = [Process(target=bulk_enhancer.run_image_enhancer, args=(f'Process-{idx}',)) for idx in range(int(args.num_threads))]
    start_time = time.perf_counter()
    for process in enhancer_process:
        process.start()
    for process in enhancer_process:
        process.join()
    finish_time = time.perf_counter()
    with open(os.path.join(args.output_dir, "output.txt"), 'w') as f:
        f.writelines([repr(bulk_enhancer),
                      "Program finished in {} seconds".format(finish_time - start_time)
                      ])
