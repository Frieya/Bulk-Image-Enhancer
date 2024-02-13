import argparse
from pydantic import BaseModel
from collections import deque
from threading import *
import glob
import os
import time
from PIL import Image,ImageEnhance

Image.MAX_IMAGE_PIXELS = None

class Enhancement(BaseModel):
        brightness_factor: int = 1
        contrast_factor: int = 1
        sharpness_factor: int = 1

class BulkImageEnhancer():

    def __init__(self, args) -> None:
        self.enhancement_factors = Enhancement(
                brightness_factor=args.brightness_factor,
                contrast_factor=args.contrast_factor,
                sharpness_factor=args.sharpness_factor
                )
        self.input_dir = args.input_dir
        self.output_dir = args.output_dir
        self.image_list = self.get_image_dir()
        self.get_from_queue = BoundedSemaphore(1)
        pass
    
    def get_image_dir(self):
        png_image_list = glob.glob(os.path.join(self.input_dir,'*.png'))
        jpg_image_list = glob.glob(os.path.join(self.input_dir,'*.jpg'))
        gif_image_list = glob.glob(os.path.join(self.input_dir,'*.gif'))
        return deque([*png_image_list, *jpg_image_list, *gif_image_list])

    def enhance_image(self, original_image):
        enhancement = self.enhancement_factors
        brightness_enhancer = ImageEnhance.Brightness(original_image)
        brightness_image = brightness_enhancer.enhance(enhancement.brightness_factor) 
        contrast_enhancer = ImageEnhance.Contrast(brightness_image)
        contrast_image = contrast_enhancer.enhance(enhancement.contrast_factor) 
        sharpness_enhancer = ImageEnhance.Sharpness(contrast_image)
        sharpen_image = sharpness_enhancer.enhance(enhancement.sharpness_factor) 
        return sharpen_image

    def process_image(self, input_image: str, output_image: str):
        image = Image.open(input_image)
        enhanced_image = self.enhance_image(image)
        enhanced_image.save(output_image)

    def get_image_to_process(self, thread_name):
        while True:
            self.get_from_queue.acquire()
            if len(self.image_list) == 0:
                self.get_from_queue.release()
                return True
            else:
                input_image = self.image_list.pop()
                self.get_from_queue.release()
            image_name = os.path.basename(input_image)
            output_image = os.path.join(self.output_dir, f"enhanced_{image_name}")
            self.process_image(input_image, output_image)
            print(f"{thread_name} is done processing image {image_name}")


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
    args =  parse_args()
    bulk_enhancer = BulkImageEnhancer(args)
    enhancer_threads = [Thread(target = bulk_enhancer.get_image_to_process, args = (f'Thread-{idx}',)) for idx in range(int(args.num_threads))]
    start_time = time.perf_counter()
    for thread in enhancer_threads:
        thread.start()
    for thread in enhancer_threads:
        thread.join()
    finish_time = time.perf_counter()
    print("Program finished in {} seconds".format(finish_time-start_time))

    
    
