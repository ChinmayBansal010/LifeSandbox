"""Text cleanup for user-facing speech synthesis."""


def _omit_fenced_code(text: str) -> str:
    parts = []
    cursor = 0
    while True:
        start = text.find("```", cursor)
        if start == -1:
            parts.append(text[cursor:])
            break
        end = text.find("```", start + 3)
        if end == -1:
            parts.append(text[cursor:])
            break
        parts.append(text[cursor:start])
        parts.append(" Code block omitted. ")
        cursor = end + 3
    return "".join(parts)


def _unwrap_inline_code(text: str) -> str:
    parts = []
    cursor = 0
    while cursor < len(text):
        start = text.find("`", cursor)
        if start == -1:
            parts.append(text[cursor:])
            break
        end = text.find("`", start + 1)
        if end == -1:
            parts.append(text[cursor:])
            break
        parts.append(text[cursor:start])
        parts.append(text[start + 1 : end])
        cursor = end + 1
    return "".join(parts)


def _unwrap_markdown_links(text: str) -> str:
    parts = []
    cursor = 0
    while cursor < len(text):
        start = text.find("[", cursor)
        if start == -1:
            parts.append(text[cursor:])
            break

        label_start = start + 1
        is_image = start > 0 and text[start - 1] == "!"
        link_end = text.find("](", label_start)
        if link_end == -1:
            parts.append(text[cursor : start + 1])
            cursor = start + 1
            continue

        closing = text.find(")", link_end + 2)
        if closing == -1 or link_end == label_start:
            parts.append(text[cursor : start + 1])
            cursor = start + 1
            continue

        parts.append(text[cursor : start - 1 if is_image else start])
        parts.append(text[label_start:link_end])
        cursor = closing + 1
    return "".join(parts)


def _strip_line_prefixes(text: str) -> str:
    lines = []
    for line in text.splitlines():
        index = 0
        while index < len(line) and line[index] in " \t" and index < 3:
            index += 1

        if index <= 3 and index < len(line) and line[index] == "#":
            marker_end = index
            while marker_end < len(line) and line[marker_end] == "#":
                marker_end += 1
            if marker_end - index <= 6:
                index = marker_end
                while index < len(line) and line[index].isspace():
                    index += 1
                line = line[index:]
        else:
            list_index = index
            if list_index < len(line) and line[list_index] in "-*+":
                marker_end = list_index + 1
                if marker_end < len(line) and line[marker_end].isspace():
                    while marker_end < len(line) and line[marker_end].isspace():
                        marker_end += 1
                    line = line[marker_end:]
            else:
                marker_end = list_index
                while marker_end < len(line) and line[marker_end].isdigit():
                    marker_end += 1
                if marker_end > list_index and marker_end < len(line) and line[marker_end] in ".)":
                    marker_end += 1
                    if marker_end < len(line) and line[marker_end].isspace():
                        while marker_end < len(line) and line[marker_end].isspace():
                            marker_end += 1
                        line = line[marker_end:]
        lines.append(line)
    return "\n".join(lines)


def speech_text(markdown: str) -> str:
    text = _omit_fenced_code(markdown)
    text = _unwrap_inline_code(text)
    text = _unwrap_markdown_links(text)
    text = _strip_line_prefixes(text)
    text = text.replace("|", ", ")
    text = text.translate(str.maketrans("", "", "*_~"))
    return " ".join(text.split()).strip()
