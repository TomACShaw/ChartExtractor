from PIL import Image, ImageDraw

"""

This script creates visualizations of intraoperative charts from pixel coordinate data.
The final version will take a JSON file of detections as input and output a PNG with the corresponding
blood pressure and heart rate data. This version uses hard-coded numbers to show proof of concept.

Each detection will be converted to a tuple of (x, y) coordinates in pixels and added to
a list of coordinates.

Asset Pixel Data:

chart is 3300x2550
sys_arrow and dia_arrow are 20x15 
dot is 10x10

"""


# Open required asset files as Image objects
chart = Image.open("../assets/blank_sheet.png")
sys_arrow = Image.open("../assets/systolic_arrow.png")
dot = Image.open("../assets/dot.png")
dia_arrow = Image.open("../assets/diastolic_arrow.png")


if __name__ == "__main__":

    sys_detections: list[tuple] = [(537, 1002), (597, 1042), (897, 1034)]
    dot_detections: list[tuple] = [(542, 1052), (602, 1092), (902, 1251)]
    dia_detections: list[tuple] = [(537, 1097), (597, 1137), (897, 1456)]
    asset = Image.new(mode="RGBA", size=chart.size, color=(255, 255, 255, 0))

    for coords in sys_detections:
        asset.paste(im=sys_arrow, box=coords)
        chart = Image.alpha_composite(chart, asset)
    for coords in dot_detections:
        asset.paste(im=dot, box=coords)
        chart = Image.alpha_composite(chart, asset)
    for coords in dia_detections:
        asset.paste(im=dia_arrow, box=coords)
        chart = Image.alpha_composite(chart, asset)

    chart.save("output.png")
