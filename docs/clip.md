# The Clip tab

The **Clip** tab turns one source video into one or more outputs. Each output is
a combination of an optional **crop** (a rectangle in space) and an optional
**trim** (a range in time) — so a clip can be a crop, a trim, or both.

![The Clip tab](assets/app-clip-light.png#only-light){ loading=lazy }
![The Clip tab](assets/app-clip-dark.png#only-dark){ loading=lazy }

## Open one or more videos

Drop videos onto the canvas or use **Add video…** (you can select or drag in
several at once). They collect in the left **Videos** list, and each open clip
keeps its own crops, trims, encoding, output folder, and preview frame.

- **Duplicate** reuses the selected clip's crops, trims, and settings — handy for
  trying a variation.
- **Remove** drops the selected clip.

## Pick a preview frame

The **Preview frame** box extracts any frame of the video so you can see what
you're cropping (useful when a clip starts on black). Type a frame number and
click **Reload**. On a long recording this seek is fast — it jumps straight to
the frame rather than decoding from the start.

## Draw crops

- **Click-and-drag** on the frame to draw a crop box.
- **Click a box** to select it; drag the body to move it, drag a handle to resize.
  The selection is mirrored in the **Crops** list (and vice-versa).
- **Delete** / **Backspace** removes the selected box.

Each box becomes one output. With no crop at all, the whole frame is used.

## Set trims (time ranges)

The **Trim** panel cuts the video in time. Type a **Start** and **End** as either
a frame number or a timecode (`HH:MM:SS.mmm`) — switch the unit with the toggle —
then click **Add trim**. A trim usually runs *to the end*, so the **⤓** button on
the **End** field jumps to the last frame; the one on **Start** grabs whatever the
preview is currently showing.

With no trim, the whole timeline is used.

!!! tip "Finding cut points"
    Scrub the **Preview frame** to a moment, then use the **⤓** buttons to drop
    that frame straight into Start or End — no separate scrubber needed, and it's
    frame-accurate however long the video is.

## One output per crop × trim

croppy makes one file for **every crop combined with every trim**. Two crops and
three trims make six files, and the queue button shows the count
(**Add 6 Jobs to Queue**). With only crops, or only trims, you just get that one
axis.

## Name the output

The **Output** box sets where files land (**Folder**) and what they're called
(**Basename**, seeded from the source name). A single output keeps the basename
verbatim; when there are several, croppy appends `_crop1`, `_trim1`, … so they
stay distinct. See [Output names & the Jobs queue](output-and-jobs.md) for the
full naming rules.

## Queue it

**Add Job to Queue** stages every crop × trim on the [Jobs tab](output-and-jobs.md);
a short confirmation flashes so you know it landed. The encoding used is whatever
the **Encoding** panel shows for this clip — see [Encoding & presets](encoding.md).
