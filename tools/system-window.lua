-- Style only blockquotes explicitly headed "System".
-- Other blockquotes, such as the Product User Manual, stay ordinary quotes.

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
  if FORMAT:match("epub") then
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

  -- One fixed-layout table keeps decorative images out of nested auto-width
  -- cells, which collapse under reader-wide img { max-width: 100% } rules.
  local function picture(name, width, height)
    return pandoc.Image(
      {},
      ornament(name),
      "",
      pandoc.Attr("", {name:match("^dragon") and "system-dragon" or "system-corner-art"},
        {width = tostring(width), height = tostring(height)})
    )
  end

  local function cell(content, classes, colspan)
    local blocks = content.t and {content} or content
    return pandoc.Cell(
      blocks,
      pandoc.AlignCenter,
      1,
      colspan or 1,
      pandoc.Attr("", classes)
    )
  end

  local function plain(inlines, classes, colspan)
    return cell(pandoc.Plain(inlines), classes, colspan)
  end

  local function blank(classes, colspan)
    return plain({pandoc.RawInline("html", "&#160;")}, classes, colspan)
  end

  local cols = function(count)
    local specs = {}
    for _ = 1, count do
      specs[#specs + 1] = {pandoc.AlignDefault, 0}
    end
    return specs
  end

  local function grid(classes, col_count, rows)
    return pandoc.Table(
      {},
      cols(col_count),
      pandoc.TableHead(),
      {{attr = pandoc.Attr(), head = {}, body = rows, row_head_columns = 0}},
      pandoc.TableFoot(),
      pandoc.Attr("", classes)
    )
  end

  local crest = {
    picture("dragon.png", 24, 19),
    pandoc.Span(block.content[1].content, pandoc.Attr("", {"system-plaque"})),
    picture("dragon-flip.png", 24, 19),
  }

  local body = {}
  for index = 2, #block.content do
    body[#body + 1] = block.content[index]
  end

  return grid({"system-window"}, 5, {
    pandoc.Row({
      plain({picture("corner-tl.png", 24, 24)}, {"system-corner", "system-corner-top"}),
      plain({pandoc.Span({}, pandoc.Attr("", {"system-bar"}))}, {"system-rail"}),
      plain({pandoc.Span(crest, pandoc.Attr("", {"system-crest-content"}))}, {"system-crest"}),
      plain({pandoc.Span({}, pandoc.Attr("", {"system-bar"}))}, {"system-rail"}),
      plain({picture("corner-tr.png", 24, 24)}, {"system-corner", "system-corner-top"}),
    }),
    pandoc.Row({
      blank({"system-edge", "system-edge-left"}),
      cell(body, {"system-body"}, 3),
      blank({"system-edge", "system-edge-right"}),
    }),
    pandoc.Row({
      plain({picture("corner-bl.png", 24, 24)}, {"system-corner", "system-corner-bottom"}),
      blank({"system-base"}, 3),
      plain({picture("corner-br.png", 24, 24)}, {"system-corner", "system-corner-bottom"}),
    }),
  })
end
