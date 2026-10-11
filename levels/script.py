door = None

def on_load(ctx):
  global door
  door = ctx.by_id("door")
  if door is None:
    raise RuntimeError("door not found")
    return
  ctx.log(f"loaded door")

def on_enter(ctx):
  ctx.log("a")