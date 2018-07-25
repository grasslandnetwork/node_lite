# Taken from https://github.com/tensorflow/models/blob/master/research/object_detection/utils/visualization_utils.py

def draw_mask_on_image_array(
        image,
        mask,
        color='red',
        alpha=0.4):
    """Draws mask on an image.
    Args:
    image: uint8 numpy array with shape (img_height, img_height, 3)
    mask: a uint8 numpy array of shape (img_height, img_height) with
    values between either 0 or 1.
    color: color to draw the keypoints with. Default is red.
    alpha: transparency value between 0 and 1. (default: 0.4)
    Raises:
    ValueError: On incorrect data type for image or masks.
    """
    if image.dtype != np.uint8:
        raise ValueError('`image` not of type np.uint8')
    if mask.dtype != np.uint8:
        raise ValueError('`mask` not of type np.uint8')
    if np.any(np.logical_and(mask != 1, mask != 0)):
        raise ValueError('`mask` elements should be in [0, 1]')
    if image.shape[:2] != mask.shape:
        raise ValueError('The image has spatial dimensions %s but the mask has '
                         'dimensions %s' % (image.shape[:2], mask.shape))
    rgb = ImageColor.getrgb(color)
    pil_image = Image.fromarray(image)

    solid_color = np.expand_dims(
        np.ones_like(mask), axis=2) * np.reshape(list(rgb), [1, 1, 3])
    pil_solid_color = Image.fromarray(np.uint8(solid_color)).convert('RGBA')
    pil_mask = Image.fromarray(np.uint8(255.0*alpha*mask)).convert('L')
    pil_image = Image.composite(pil_solid_color, pil_image, pil_mask)
    np.copyto(image, np.array(pil_image.convert('RGB')))

  
def draw_keypoints_on_image_array(
        image,
        keypoints,
        color='red',
        radius=2,
        use_normalized_coordinates=True):
    """Draws keypoints on an image (numpy array).
    Args:
    image: a numpy array with shape [height, width, 3].
    keypoints: a numpy array with shape [num_keypoints, 2].
    color: color to draw the keypoints with. Default is red.
    radius: keypoint radius. Default value is 2.
    use_normalized_coordinates: if True (default), treat keypoint values as
    relative to the image.  Otherwise treat them as absolute.
    """
    image_pil = Image.fromarray(np.uint8(image)).convert('RGB')
    draw_keypoints_on_image(image_pil, keypoints, color, radius,
                            use_normalized_coordinates)
    
    np.copyto(image, np.array(image_pil))

  
def draw_bounding_box_on_image_array(
        image,
        ymin,
        xmin,
        ymax,
        xmax,
        color='red',
        thickness=4,
        display_str_list=(),
        use_normalized_coordinates=True):
    """Adds a bounding box to an image (numpy array).
    Bounding box coordinates can be specified in either absolute (pixel) or
    normalized coordinates by setting the use_normalized_coordinates argument.
    Args:
    image: a numpy array with shape [height, width, 3].
    ymin: ymin of bounding box.
    xmin: xmin of bounding box.
    ymax: ymax of bounding box.
    xmax: xmax of bounding box.
    color: color to draw bounding box. Default is red.
    thickness: line thickness. Default value is 4.
    display_str_list: list of strings to display in box
    (each to be shown on its own line).
    use_normalized_coordinates: If True (default), treat coordinates
    ymin, xmin, ymax, xmax as relative to the image.  Otherwise treat
    coordinates as absolute.
    """
    image_pil = Image.fromarray(np.uint8(image)).convert('RGB')
    draw_bounding_box_on_image(image_pil, ymin, xmin, ymax, xmax, color,
                               thickness, display_str_list,
                               use_normalized_coordinates)
    np.copyto(image, np.array(image_pil))

  

def visualize_boxes_and_labels_on_image_array(
        image,
        boxes,
        classes,
        scores,
        category_index,
        instance_masks=None,
        instance_boundaries=None,
        keypoints=None,
        use_normalized_coordinates=False,
        max_boxes_to_draw=20,
        min_score_thresh=.5,
        agnostic_mode=False,
        line_thickness=4,
        groundtruth_box_visualization_color='black',
        skip_scores=False,
        skip_labels=False):
    """Overlay labeled boxes on an image with formatted scores and label names.
    This function groups boxes that correspond to the same location
    and creates a display string for each detection and overlays these
    on the image. Note that this function modifies the image in place, and returns
    that same image.
    Args:
      image: uint8 numpy array with shape (img_height, img_width, 3)
      boxes: a numpy array of shape [N, 4]
      classes: a numpy array of shape [N]. Note that class indices are 1-based,
        and match the keys in the label map.
      scores: a numpy array of shape [N] or None.  If scores=None, then
        this function assumes that the boxes to be plotted are groundtruth
        boxes and plot all boxes as black with no classes or scores.
      category_index: a dict containing category dictionaries (each holding
        category index `id` and category name `name`) keyed by category indices.
      instance_masks: a numpy array of shape [N, image_height, image_width] with
        values ranging between 0 and 1, can be None.
      instance_boundaries: a numpy array of shape [N, image_height, image_width]
        with values ranging between 0 and 1, can be None.
      keypoints: a numpy array of shape [N, num_keypoints, 2], can
        be None
      use_normalized_coordinates: whether boxes is to be interpreted as
        normalized coordinates or not.
      max_boxes_to_draw: maximum number of boxes to visualize.  If None, draw
        all boxes.
      min_score_thresh: minimum score threshold for a box to be visualized
      agnostic_mode: boolean (default: False) controlling whether to evaluate in
        class-agnostic mode or not.  This mode will display scores but ignore
        classes.
      line_thickness: integer (default: 4) controlling line width of the boxes.
      groundtruth_box_visualization_color: box color for visualizing groundtruth
        boxes
      skip_scores: whether to skip score when drawing a single detection
      skip_labels: whether to skip label when drawing a single detection
    Returns:
      uint8 numpy array with shape (img_height, img_width, 3) with overlaid boxes.
    """
    # Create a display string (and color) for every box location, group any boxes
    # that correspond to the same location.
    box_to_display_str_map = collections.defaultdict(list)
    box_to_color_map = collections.defaultdict(str)
    box_to_instance_masks_map = {}
    box_to_instance_boundaries_map = {}
    box_to_keypoints_map = collections.defaultdict(list)
    if not max_boxes_to_draw:
        max_boxes_to_draw = boxes.shape[0]
    for i in range(min(max_boxes_to_draw, boxes.shape[0])):
        if scores is None or scores[i] > min_score_thresh:
            box = tuple(boxes[i].tolist())
            if instance_masks is not None:
                box_to_instance_masks_map[box] = instance_masks[i]
            if instance_boundaries is not None:
                box_to_instance_boundaries_map[box] = instance_boundaries[i]
            if keypoints is not None:
                box_to_keypoints_map[box].extend(keypoints[i])
            if scores is None:
                box_to_color_map[box] = groundtruth_box_visualization_color
            else:
                display_str = ''
                if not skip_labels:
                    if not agnostic_mode:
                        if classes[i] in category_index.keys():
                            class_name = category_index[classes[i]]['name']
                        else:
                            class_name = 'N/A'
                        display_str = str(class_name)
                if not skip_scores:
                    if not display_str:
                        display_str = '{}%'.format(int(100*scores[i]))
                    else:
                        display_str = '{}: {}%'.format(display_str, int(100*scores[i]))
                box_to_display_str_map[box].append(display_str)
                if agnostic_mode:
                    box_to_color_map[box] = 'DarkOrange'
                else:
                    box_to_color_map[box] = STANDARD_COLORS[classes[i] % len(STANDARD_COLORS)]

    # Draw all boxes onto image.
    for box, color in box_to_color_map.items():
        ymin, xmin, ymax, xmax = box
        if instance_masks is not None:
            draw_mask_on_image_array(
                image,
                box_to_instance_masks_map[box],
                color=color
            )
        if instance_boundaries is not None:
            draw_mask_on_image_array(
                image,
                box_to_instance_boundaries_map[box],
                color='red',
                alpha=1.0
            )
        draw_bounding_box_on_image_array(
            image,
            ymin,
            xmin,
            ymax,
            xmax,
            color=color,
            thickness=line_thickness,
            display_str_list=box_to_display_str_map[box],
            use_normalized_coordinates=use_normalized_coordinates
        )
        if keypoints is not None:
            draw_keypoints_on_image_array(
                image,
                box_to_keypoints_map[box],
                color=color,
                radius=line_thickness / 2,
                use_normalized_coordinates=use_normalized_coordinates
            )

    return image

