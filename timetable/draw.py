import drawille


def text_len(text):
    ''' Return the length of some text in pixels.

    One drawille x pixel is worth 1/2 a character.

    Args:
        text (str): The text to find the length of

    Returns:
        int: The length of the text in pixels '''
    return len(text) * 2


def line(canvas, x1, y1, x2, y2):
    ''' Draw a line from (x1, y1) to (x2, y2).

    Args:
        canvas (drawille.Canvas): The canvas to draw on.
        x1 (int): Where the line starts (x-pos).
        y1 (int): Where the line starts (y-pos).
        x2 (int): Where the line ends (x-pos).
        y2 (int): Where the line ends (y-pos). '''
    for x, y in drawille.line(x1, y1, x2, y2):
        canvas.set(x, y)


def box(canvas, x, y, width, height, contents):
    ''' Draw a box with some text in it.

    Args:
        canvas (drawille.Canvas): The canvas to draw on.
        x (int): The top left of the box (x-pos).
        y (int): The top left of the box (y-pos).
        width (int): The width of the box.
        height (int): The height of the box.
        contents (str): Text to put in the box. '''
    lines = contents.split('\n')
    # Top of box
    line(canvas, x, y, x + width, y)
    # Bottom of box
    line(canvas, x, y + height, x + width, y + height)
    # Left of box
    line(canvas, x, y, x, y + height)
    # Right of box
    line(canvas, x + width, y, x + width, y + height)
    for y_l, text_line in zip(range(y + 4, y + height, 4), lines):
        canvas.set_text(x + 4, y_l, text_line)


def timeline(canvas, x, y, box_width, box_height, mapping):
    ''' Draw a timeline using keys and values of a dictionary.

    Args:
        canvas (drawille.Canvas): The canvas to draw on.
        x (int): Top left of timeline (x-pos).
        y (int): Top left of timeline (x-pos).
        box_width (int): The width of the boxes to draw around timeline items
        box_width (int): The height of the boxes to draw around timeline items.
        mapping (OrderedDict): A mapping of keys (on the left of the
                               dividing line), and values (on the
                               right of the dividing line).

    Examples:
        See timeline.png for an example output. '''
    # We need to pad out the divider of the timeline to put it, so we
    # take the max of the keys (to be on the left of the timeline),
    # and add 2 pixels for some aesthetic padding.
    left_padding = max(text_len(text) for text in mapping) + 2
    # To calculate the height of the timeline, we need to take the
    # number of keys and multiply that by the box height + 4 pixels of
    # padding in between each box.
    timeline_end = y + len(mapping) * (box_height + 4)
    # Draw the dividing line
    line(canvas, x + left_padding, y, x + left_padding, timeline_end)
    for y_l, key in zip(range(y, timeline_end, box_height + 4), mapping):
        # Draw the key on the left of the dividing line.
        canvas.set_text(x, y_l, key)
        values = mapping[key]
        # Starting from a comfortable padding from the dividing line
        x_start = x + left_padding + 4
        # Draw a set of boxes, separated by 4 pixels of padding.
        for value in values:
            box(canvas, x_start, y_l, box_width, box_height, value)
            x_start += box_width + 4
