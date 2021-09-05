colors = { SILE.colorparser("red"), SILE.colorparser("green"), SILE.colorparser("blue") }
cur_word = 0

SILE.nodeMakers.unicode.makeGlue = function(self, item)
 coroutine.yield(SILE.nodefactory.hbox({
    outputYourself = function()
        cur_word = (cur_word + 1)
        if cur_word > 0 then SILE.outputter:popColor() end
        SILE.outputter:pushColor(colors[cur_word % 3 + 1])
    end }))
  coroutine.yield(SILE.shaper:makeSpaceNode(self.options, item))
  self.lastnode = "glue"
end
