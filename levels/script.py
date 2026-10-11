door = None

def on_load(ctx):
  global door
  door = ctx.by_id("door")
  if door is None:
    raise RuntimeError("door not found")
    return
  ctx.log(f"loaded door")
  print(door.body.position.y)

def on_enter(ctx):
  ctx.move_to(door, y=500, dur=0.6, ease="out")

def on_exit(ctx):
  ctx.move_to(door, y=158, dur=0.6, ease="out")