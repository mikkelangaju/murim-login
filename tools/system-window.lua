-- Style only blockquotes explicitly headed "System".
-- Other blockquotes, such as the Product User Manual, stay ordinary quotes.
local full_color_epub = false

function Meta(meta)
  full_color_epub = meta["full-color-epub"] == true
end

local function is_system(block)
  local first = block.content[1]
  return first and first.t == "Para" and pandoc.utils.stringify(first) == "System"
end

local function ornament(name)
  local script_dir = pandoc.path.directory(PANDOC_SCRIPT_FILE)
  local repo = pandoc.path.directory(script_dir)
  return pandoc.path.join({repo, "reader", "src", "ornaments", name})
end

-- Raw HTML breaks are valid in HTML but must be closed in EPUB XHTML.
function RawInline(inline)
  if FORMAT:match("epub") and inline.format == "html" then
    if inline.text:lower():match("^<br%s*/?>$") then
      return pandoc.LineBreak()
    end
    -- Capitalized bracketed names are prose labels, not HTML elements.
    if inline.text:match("^<%u[%w%s]*>$") then
      return pandoc.Str(inline.text)
    end
  end
end

-- File-scope wrappers otherwise hide chapter headings from EPUB splitting.
-- Keep file-scope parsing so repeated footnote labels stay chapter-local.
function Div(block)
  if FORMAT:match("epub") and block.identifier:match("%.md$")
      and #block.classes == 0 then
    return block.content
  end
end

function HorizontalRule()
  if FORMAT:match("epub") and full_color_epub then
    return pandoc.Div({pandoc.Plain({pandoc.Image(
      {}, ornament("yin-yang.png"), "",
      pandoc.Attr("", {"scene-separator-art"}, {width = "22", height = "22"})
    )})}, pandoc.Attr("", {"scene-separator"}, {role = "separator"}))
  end
  if not FORMAT:match("typst") then
    return nil
  end
  return pandoc.RawBlock("typst", string.format(
    '#align(center, block(above: 1.6em, below: 1.6em, image("%s", width: 1.35em)))',
    ornament("yin-yang.svg")
  ))
end

function BlockQuote(block)
  if not is_system(block) then
    return block
  end

  if FORMAT:match("typst") then
    local result = {
      pandoc.RawBlock("typst", string.format(
        '#murim-plaque("%s", "%s")[',
        ornament("corner.svg"),
        ornament("dragon.svg")
      )),
    }
    for index = 2, #block.content do
      table.insert(result, block.content[index])
    end
    table.insert(result, pandoc.RawBlock("typst", "]"))
    return result
  end

  if FORMAT:match("epub") and not full_color_epub then
    local body = {}
    for index = 2, #block.content do
      body[#body + 1] = block.content[index]
    end
    return pandoc.Div({
      pandoc.Div({pandoc.Plain({pandoc.Str("SYSTEM")})}, pandoc.Attr("", {"system-title"})),
      pandoc.Div(body, pandoc.Attr("", {"system-body"})),
    }, pandoc.Attr("", {"system-window-simple"}))
  end

  -- One cell preserves Books' table zoom and avoids decorative column sizing.
  -- The entire crest is in flow, including its space above the top gold rail.
  local function picture(name, width, height, classes)
    return pandoc.Image({}, ornament(name), "",
      pandoc.Attr("", classes, {width = tostring(width), height = tostring(height)}))
  end
  local function div(blocks, class)
    return pandoc.Div(blocks, pandoc.Attr("", {class}))
  end
  local crest = div({pandoc.Plain({
    picture("dragon.png", 24, 19, {"system-dragon"}),
    pandoc.Span(block.content[1].content, pandoc.Attr("", {"system-plaque"})),
    picture("dragon-flip.png", 24, 19, {"system-dragon"}),
  })}, "system-crest")
  local header = div({
    pandoc.Plain({
      picture("corner-tl.png", 24, 24, {"system-corner-art", "system-corner-tl"}),
      picture("corner-tr.png", 24, 24, {"system-corner-art", "system-corner-tr"}),
    }),
    crest,
  }, "system-header")
  local body = {}
  for index = 2, #block.content do body[#body + 1] = block.content[index] end
  local footer = div({pandoc.Plain({
    picture("corner-bl.png", 24, 24, {"system-corner-art", "system-corner-bl"}),
    picture("corner-br.png", 24, 24, {"system-corner-art", "system-corner-br"}),
  })}, "system-footer")
  local content = {
    header,
    div({div(body, "system-body")}, "system-content"),
    footer,
  }
  local cell = pandoc.Cell(content, pandoc.AlignCenter, 1, 1,
    pandoc.Attr("", {"system-cell"}))
  return pandoc.Table({}, {{pandoc.AlignDefault, 0}}, pandoc.TableHead(),
    {{attr = pandoc.Attr(), head = {}, body = {pandoc.Row({cell})}, row_head_columns = 0}},
    pandoc.TableFoot(), pandoc.Attr("", {"system-window"}))
end

-- Read the option before walking blocks; default Lua traversal visits Meta last.
return {
  {Meta = Meta},
  {RawInline = RawInline, Div = Div, HorizontalRule = HorizontalRule, BlockQuote = BlockQuote},
}
