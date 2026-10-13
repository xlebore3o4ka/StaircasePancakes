btn1 = None
btn2 = None
door = None
opened = False

def on_load(ctx):
  global btn1, btn2, door
  btn1 = ctx.by_id("my_button1")
  if btn1 is None:
    raise RuntimeError("btn1 not found")
  ctx.log(f"loaded btn1")

  btn2 = ctx.by_id("my_button2")
  if btn2 is None:
    raise RuntimeError("btn2 not found")
  ctx.log(f"loaded btn2")
  
  door = ctx.by_id("door")
  if door is None:
    raise RuntimeError("door not found")
  ctx.log(f"loaded door")

def open_door(ctx):
  global opened
  ctx.move_to(door, y=500, dur=0.5, ease="inout")
  opened = True

def close_door(ctx):
  global opened
  ctx.move_to(door, y=178, dur=0.5, ease="inout")
  opened = False

def on_button_up(ctx, tag):
  if tag in {"my_button1", "my_button2"}:
    if opened: close_door(ctx)
    else: open_door(ctx)