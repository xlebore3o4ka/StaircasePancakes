btn = None

def on_load(ctx):
  global btn
  btn = ctx.by_id("my_button")
  if btn is None:
    raise RuntimeError("btn not found")
    return
  ctx.log(f"loaded btn")

def on_button_up(ctx, tag):
  if tag == "my_button":
    print(1)