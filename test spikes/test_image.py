import argparse
from pydantic import BaseModel
from multiprocessing import Process, Queue
import glob
import os
import time
from PIL import Image, ImageEnhance
from multiprocessing import set_start_method
import io
import base64
import matplotlib.pyplot as plt

image = Image.open("input/image-1.jpg")
buf = io.BytesIO()
image.save(buf, format='JPEG')
b_image = buf.getvalue()
print(b_image)
