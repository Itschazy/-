import json
import logging
from PIL import Image, ImageDraw, ImageFont, ImageColor

logger = logging.getLogger('app.drawing')

with open('assets/library.json', encoding='utf-8') as f:
    library = json.load(f)


def get_position(initial, size, alignment):
    if alignment == "left":
        return (
            initial[0],
            initial[1] - size[1] / 2
        )
    elif alignment == "center":
        return (
            initial[0] - size[0] / 2,
            initial[1] - size[1] / 2
        )
    elif alignment == "right":
        return (
            initial[0] - size[0],
            initial[1] - size[1] / 2
        )
    else:
        raise ValueError("Unknown alignment: " + str(alignment))


def check_text_cropping(position, text_size, image_size):
    is_inside = (0 <= position[0] <= image_size[0]) \
        and (0 <= position[1] <= image_size[1]) \
        and (0 <= position[0] + text_size[0] <= image_size[0]) \
        and (0 <= position[1] + text_size[1] <= image_size[1])
    return not is_inside


def add_text_layer(image, stage, text):
    COLOR_TRANSPARENT = (255, 255, 255, 0)

    font_size = stage['font']['size']

    if 'family' in stage['font']:
        font = ImageFont.truetype(stage['font']['family'], size=font_size)
    elif 'file' in stage['font']:
        font = ImageFont.truetype('./assets/' + stage['font']['file'], size=font_size)
    
    fill_color = ImageColor.getcolor(stage['font']['fill'], "RGB")
    stroke_color = ImageColor.getcolor(stage['font']['stroke'], "RGB")
    stroke_width = stage['font']['stroke_width']

    alignment = stage['align']

    text_layer = Image.new('RGBA', image.size, COLOR_TRANSPARENT)
    text_context = ImageDraw.Draw(text_layer)

    is_cropped = True
    resize_counter = 0
    scale = 1

    while is_cropped:
        text_size = text_context.textsize(text, font=font, stroke_width=stroke_width)
        
        position = get_position((stage['x'], stage['y']), text_size, alignment)

        is_cropped = check_text_cropping(position, text_size, image.size)

        if is_cropped:
            scale = 0.97 * scale
            font = font.font_variant(size=int(round(scale * font_size)))
            resize_counter += 1
            if scale < 0.01:
                logger.warning("Scale too small, giving up...")
                break
    
    logger.info("Text resized {0} times, new scale: {1}".format(resize_counter, scale))

    text_context.text(
        position, text,
        align=alignment,
        font=font,
        fill=fill_color,
        stroke_fill=stroke_color,
        stroke_width=int(round(scale * stroke_width))
    )

    if 'shadow' in stage:
        shadow_offset = (scale * stage['shadow']['offset_x'], scale * stage['shadow']['offset_y'])
        shadow_alpha = stage['shadow']['alpha']
        shadow_color = (0, 0, 0, int(round(shadow_alpha * 255)))

        shadow_thickness = stage['shadow']['thickness']

        shadow_layer = Image.new('RGBA', image.size, COLOR_TRANSPARENT)
        shadow_context = ImageDraw.Draw(shadow_layer)
        shadow_context.text(
            (position[0] + shadow_offset[0], position[1] + shadow_offset[1]), text,
            align=alignment,
            font=font,
            fill=shadow_color,
            stroke_fill=shadow_color,
            stroke_width=int(round(scale * (stroke_width + shadow_thickness)))
        )

        text_layer = Image.alpha_composite(shadow_layer, text_layer)
    
    if 'affine' in stage['font']:
        text_layer = text_layer.transform(
            text_layer.size, Image.AFFINE, stage['font']['affine']
        )
    
    return Image.alpha_composite(image, text_layer)


def create_postcard(template, texts, filename='assets/temp.png'):

    queries = template['queries']

    with Image.open('assets/' + template['filename']).convert('RGBA') as src_image:
        result = src_image
        for query in queries:
            result = add_text_layer(result, query, texts[query['id']])

        result.save(filename)
