import time
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def get_noise(size=(500, 500), min=(0, 0, 0), max=(100, 100, 200), blur=5):
    noise_map = np.random.randint(
        [min[0], min[1], min[2]],
        [max[0] + 1, max[1] + 1, max[2] + 1],
        (size[1], size[0], 3),
        dtype=np.uint8
    )
    img = Image.fromarray(noise_map)
    if blur > 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=blur))
    return img

def logo(size = (200, 200)):
    img = Image.new('RGB', size, color='#000')
    draw = ImageDraw.Draw(img)

    w, h = size
    size_avrige = (w + h) // 2

    def s(val):
        return (size_avrige * val) // 100
    
    img.save('logo.png')


def banner(size = (200, 200)):
    img = Image.new('RGB', size, color='#fff')
    draw = ImageDraw.Draw(img)

    w, h = size
    size_avrige = (w + h) // 2

    def s(val):
        return (size_avrige * val) // 100

    noise = get_noise(min=[0,0,0], max = [100,100,200], size=size)
    img.paste(noise)
    draw = ImageDraw.Draw(img)

    for i in range(-9, 10):
        i *= s(10)
        draw.line([(i+0.1*w, 0.1*h), (i+0.9*w, 0.9*h)], width=s(5))

    img.save('banner.png')



start_time = time.perf_counter()
logo(size=(500, 500))
end_time = time.perf_counter()
print(f'time: {end_time - start_time:.10f}s')

