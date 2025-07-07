from PIL import Image, ImageDraw


# Open required asset files as Image objects
chart = Image.open("../assets/blank_sheet.png")
sys_arrow = Image.open("../assets/systolic_arrow.png")
dot = Image.open("../assets/dot.png")
dia_arrow = Image.open("../assets/diastolic_arrow.png")

# chart is 3300x2550
# sys_arrow is 20x15 
# dot is 10x10
# dia_arrow is 20x15



if __name__ == "__main__":

    sys_coords: list[tuple] = [(537, 1002), (597, 1042), (897, 1034)]
    dot_coords: list[tuple] = [(542, 1052), (602, 1092), (902, 1251)]
    dia_coords: list[tuple] = [(537, 1097), (597, 1137), (897, 1456)]
    asset = Image.new(mode="RGBA", size=chart.size, color=(255, 255, 255, 0))

    for coords in sys_coords:
        asset.paste(im=sys_arrow, box=coords)
        chart = Image.alpha_composite(chart, asset)
    for coords in dot_coords:
        asset.paste(im=dot, box=coords)
        chart = Image.alpha_composite(chart, asset)
    for coords in dia_coords:
        asset.paste(im=dia_arrow, box=coords)
        chart = Image.alpha_composite(chart, asset)

    chart.save("output.png")
