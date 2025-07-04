import sys
from PIL import Image, ImageDraw

'''Arguments:
    background: the PNG file the arrow will be drawn on
    init_x: the x-coordinate of the initial pixel
    init_y: the y-coordinate of the initial pixel'''

def draw_diastolic_arrow(background: str, init_x: int, init_y: int) -> Image:

    bg = Image.open(background)
    with Image.new(mode="RGBA", size=(20, 15), color=(255, 255, 255, 0)) as base:
        arrow = Image.new(mode="RGBA", size=base.size, color=(255, 255, 255, 0))    
        draw = ImageDraw.Draw(base)
        draw.line(xy=((0, 15), (10, 0)), fill=("black"), width = 3)
        draw.line(xy=((10, 0), (20, 15)), fill=("black"), width = 3)
        out = Image.alpha_composite(base, arrow)

    bg.alpha_composite(out, (init_x, init_y))
    return bg


def draw_systolic_arrow(background: str, init_x: int, init_y: int) -> Image:

    bg = Image.open(background)
    with Image.new(mode="RGBA", size=(20, 15), color=(255, 255, 255, 0)) as base:
        arrow = Image.new(mode="RGBA", size=base.size, color=(255, 255, 255, 0))    
        draw = ImageDraw.Draw(base)
        draw.line(xy=((0, 0), (10, 15)), fill=("black"), width = 3)
        draw.line(xy=((10, 15), (20, 0)), fill=("black"), width = 3)
        out = Image.alpha_composite(base, arrow)

    bg.alpha_composite(out, (init_x, init_y))
    return bg

def draw_circle(background: str, init_x: int, init_y: int) -> Image:

    bg = Image.open(background)
    with Image.new(mode="RGBA", size=(10, 10), color=(255, 255, 255, 0)) as base:
        circle = Image.new(mode="RGBA", size=base.size, color=(255, 255, 255, 0))    
        draw = ImageDraw.Draw(base)
        draw.circle(xy=(5, 5), radius=5, fill=("black"))
        out = Image.alpha_composite(base, circle)

    bg. alpha_composite(out, (init_x, init_y))
    return bg
