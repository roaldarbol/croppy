# Tips & FAQ

### It's a very long recording (hours). Is that OK?

Yes — that's a main use case. The **Preview frame** and **Trim** marks seek
straight to a timestamp rather than decoding from the start, so jumping around a
14-hour file is quick. Set trims numerically (frame number or timecode) and add
as many as you need.

### How do I find the frame number / timecode for a trim?

Scrub the **Preview frame** to the moment you want and click the **⤓** button next
to **Start** to drop that frame in. The **End** field's **⤓** jumps to the last
frame, since trims usually run to the end.

### Does it use my GPU?

By default the **Encoder** is set to **Auto**: it encodes on your **NVIDIA
graphics card (GPU)** when you have one — much faster — and on the **CPU**
otherwise. You can force GPU or CPU in the [Encoding panel](encoding.md). The
**Parallel** toggle (Jobs tab) keeps several encodes running at once.

### Will it overwrite my files?

No. Outputs go to the folder you choose (defaulting next to the source), and if a
name would clash with an existing or already-queued file, Croppy appends
`-2`, `-3`, … Cropping/trimming/compressing always writes a *new* file; the source
is untouched.

### My cropped file kept the original's "Date created" — why?

That's the **Creation date** option (on by default, Windows only): the output
inherits the source clip's creation date, so a processed file still reflects when
the footage was recorded. Its "Date modified" shows when Croppy wrote it. Turn it
off in the Encoding panel.

### Can I make files smaller without re-cropping?

Use the [Compress tab](compress.md) — it re-encodes whole videos with your chosen
quality. To also drop the frame rate, enable **Frame rate** in the Encoding panel.

### A long combine got interrupted — did I lose it?

No. Combine writes a fragmented `.partial.mp4` and only renames it on success, so
you're left with a playable, clearly-partial file rather than a corrupt one.

### Where do outputs go?

Wherever the **Output → Folder** of that tab points — by default next to the
source file. See [Output names & the Jobs queue](output-and-jobs.md).
