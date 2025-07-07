import sys
import arrow
from PIL import Image, ImageDraw

# blank_sheet.png is 3300 x 2550
'''
with Image.open("blank_sheet.png") as base:
    
    arrow = Image.open("arrow.png")
    draw = ImageDraw.Draw(base)
    arrow_padded = Image.new("RGBA", base.size, (255, 255, 255, 0))
    # arrow_padded.paste(arrow)
    

    out = Image.alpha_composite(base, arrow_padded)
    out.save("sheet_with_arrow.png")
'''

BLANK_CHART = "/home/ajax/my-venv/test_files/assets/blank_sheet.png" 
init_x = int(sys.argv[1])
init_y = int(sys.argv[2])

if __name__ == "main":




# sheet_with_arrow = arrow.draw_arrow("/home/ajax/my-venv/test_files/assets/blank_sheet.png", 300, 300)

# sheet_with_arrow = arrow.draw_diastolic_arrow(BLANK_CHART, init_x, init_y)
    sheet_with_arrow = arrow.draw_systolic_arrow(BLANK_CHART, init_x, init_y)
    sheet_with_arrow.save("test.png")

    for i in range(10):
        init_x += 60
        init_y += 40
        sheet_with_arrow = arrow.draw_systolic_arrow("test.png", init_x, init_y)
        sheet_with_arrow.save("test.png")
        sheet_with_arrow = arrow.draw_circle("test.png", init_x, init_y + 80) 
        sheet_with_arrow.save("test.png")
        sheet_with_arrow = arrow.draw_diastolic_arrow("test.png", init_x, init_y + 160)
        sheet_with_arrow.save("test.png")
