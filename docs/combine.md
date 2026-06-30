# The Combine tab

The **Combine** tab joins several videos, in the order you choose, into a single
file. You can stage as many joins as you like by organising them into **groups**.

![The Combine tab](assets/app-combine-light.png#only-light){ loading=lazy }
![The Combine tab](assets/app-combine-dark.png#only-dark){ loading=lazy }

## Groups

Each **group** in the left list is one join: an ordered set of videos with its
own output folder, filename, and encoding.

- **New group** stages another join; **Delete** removes the selected group.
- Double-click a group to rename it. The group name is just an **organisational
  label** — it does *not* become the output filename (that's set separately,
  below).

## Build a join

Add two or more videos to the selected group and **drag to set the order** —
they're joined top-to-bottom into one file.

- **Output folder** — defaults to the first clip's location.
- **Filename** — defaults to `<first clip>_combined`, and you can change it.

## Crash-safe output

A join is written as a fragmented mp4 to a `.partial.mp4` and only renamed to its
final name once it finishes. So if a long join is interrupted, you're left with a
playable, clearly-marked partial file rather than a corrupt one.

## Queue

**Add Job to Queue** stages the **selected** group as one combine job. The group
is kept afterwards so you can tweak and re-queue it. Jobs land on the
[Jobs tab](output-and-jobs.md).

!!! note "Encoding is inherited where it can be"
    Combine always writes mp4. If you leave the **Encoder** unset (Match source),
    Croppy re-encodes using the same kind of codec as the first clip. See
    [Encoding & presets](encoding.md).
