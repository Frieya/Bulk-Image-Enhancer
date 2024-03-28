import argparse
from pydantic import BaseModel
from multiprocessing import Process, Queue
import glob
import os
import time
from PIL import Image, ImageEnhance
from multiprocessing import set_start_method

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

    def enhance_gif(self, original_image):
        enhanced_frames = []
        try:
            while True:
                current_frame = original_image.copy()
                if current_frame.mode == "P":
                    current_frame = current_frame.convert("RGBA")
                enhanced_frame = self.apply_enhancements(current_frame)
                enhanced_frames.append(enhanced_frame)
                original_image.seek(original_image.tell() + 1)
        except EOFError:
            pass  
        gif_name = os.path.basename(original_image.filename)
        gif_path = os.path.join(self.output_dir, f"enhanced_{gif_name}")
        enhanced_frames[0].save(gif_path, save_all=True, append_images=enhanced_frames[1:], loop=0)

    def enhance_image(self, original_image, output_image):
        enhanced_image = self.apply_enhancements(original_image)
        enhanced_image.save(output_image)

    def apply_enhancements(self, image):
        # Apply enhancements to the image
        enhancement = self.enhancement_factors
        brightness_enhancer = ImageEnhance.Brightness(image)
        brightness_image = brightness_enhancer.enhance(enhancement.brightness_factor)
        contrast_enhancer = ImageEnhance.Contrast(brightness_image)
        contrast_image = contrast_enhancer.enhance(enhancement.contrast_factor)
        sharpness_enhancer = ImageEnhance.Sharpness(contrast_image)
        sharpen_image = sharpness_enhancer.enhance(enhancement.sharpness_factor)
        return sharpen_image

    def process_image(self, input_image: str, output_image: str):
        image = Image.open(input_image)
        if image.format=='GIF':
            self.enhance_gif(image)
        else:
            self.enhance_image(image, output_image)      

    def get_image_to_process(self, process_name):
        while True:
            if self.image_buffer.empty():
                break
            input_image = self.image_buffer.get()
            image_name = os.path.basename(input_image)
            output_image = os.path.join(self.output_dir, f"enhanced_{image_name}")
            self.process_image(input_image, output_image)
            print(f"{process_name} is done processing image {image_name}")
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
    enhancer_process = [Process(target=bulk_enhancer.get_image_to_process, args=(f'Process-{idx}',)) for idx in range(int(args.num_threads))]
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
