from PIL import Image, ImageDraw

"""This script generates the required asset PNG files for chart visualizations if
they aren't already present in the assets folder.

Each function creates a transparent background for the asset to be drawn on to,
draws the asset, composites them together, and then saves the output as a PNG."""


def draw_systolic_arrow():
    with Image.new(mode="RGBA", size=(20, 15), color=(255, 255, 255, 0)) as base:
        systolic_arrow = Image.new(mode="RGBA", size=base.size, color=(255, 255, 255, 0))    
        draw = ImageDraw.Draw(base)
        draw.line(xy=((0, 0), (10, 15)), fill=("black"), width = 3)
        draw.line(xy=((10, 15), (20, 0)), fill=("black"), width = 3)
        out = Image.alpha_composite(systolic_arrow, base)
    out.save("systolic_arrow.png")


def draw_diastolic_arrow():
    with Image.new(mode="RGBA", size=(20, 15), color=(255, 255, 255, 0)) as base:
        diastolic_arrow = Image.new(mode="RGBA", size=base.size, color=(255, 255, 255, 0))    
        draw = ImageDraw.Draw(base)
        draw.line(xy=((0, 15), (10, 0)), fill=("black"), width = 3)
        draw.line(xy=((10, 0), (20, 15)), fill=("black"), width = 3)
        out = Image.alpha_composite(diastolic_arrow, base)
    out.save("diastolic_arrow.png")


def draw_dot():
    with Image.new(mode="RGBA", size=(10, 10), color=(255, 255, 255, 0)) as base:
        dot = Image.new(mode="RGBA", size=base.size, color=(255, 255, 255, 0))    
        draw = ImageDraw.Draw(base)
        draw.circle(xy=(5, 5), radius=5, fill=("black"))
        out = Image.alpha_composite(dot, base)
    out.save("dot.png")


if __name__ == "__main__":
    draw_systolic_arrow()
    draw_diastolic_arrow()
    draw_dot()
