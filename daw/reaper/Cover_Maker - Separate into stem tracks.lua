-- @description Cover_Maker: separate a song into stems and insert them as new tracks
-- @author Cover_Maker contributors
-- @license MIT
-- @about
--   Sends the selected media item's file (or a file or video link you type) to
--   the Cover_Maker engine running on this computer, waits for the job and
--   inserts each stem as a new track, aligned with the source item or, without
--   a selected item, at the edit cursor.
--
--   Cover_Maker must be open. The script finds the engine through the
--   per-user discovery file %LOCALAPPDATA%\Cover_Maker\run\engine.json
--   (ADR-008) and talks to it with the curl.exe that ships with Windows.
--   Only separate audio you have the right to use.

local SCRIPT = "Cover_Maker"
local STEMS = { "vocals", "drums", "bass", "guitar", "piano", "other" }
local POLL_SECONDS = 1.0

---------------------------------------------------------------------------
-- Minimal JSON (objects, arrays, strings, numbers, booleans, null)
---------------------------------------------------------------------------

local json = {}

local escapes = { ['"'] = '\\"', ["\\"] = "\\\\", ["\b"] = "\\b", ["\f"] = "\\f",
  ["\n"] = "\\n", ["\r"] = "\\r", ["\t"] = "\\t" }

local function encode_string(s)
  return '"' .. s:gsub('[%c"\\]', function(c)
    return escapes[c] or string.format("\\u%04x", c:byte())
  end) .. '"'
end

function json.encode(value)
  local kind = type(value)
  if kind == "nil" then return "null" end
  if kind == "boolean" then return tostring(value) end
  if kind == "number" then return string.format("%.14g", value) end
  if kind == "string" then return encode_string(value) end
  if kind == "table" then
    local parts = {}
    if #value > 0 then
      for _, v in ipairs(value) do parts[#parts + 1] = json.encode(v) end
      return "[" .. table.concat(parts, ",") .. "]"
    end
    for k, v in pairs(value) do
      if k ~= "__array" then parts[#parts + 1] = encode_string(tostring(k)) .. ":" .. json.encode(v) end
    end
    return "{" .. table.concat(parts, ",") .. "}"
  end
  error("cannot encode " .. kind)
end

function json.decode(text)
  local pos = 1
  local function skip() pos = text:find("[^ \t\r\n]", pos) or #text + 1 end
  local value
  local function str()
    local out, i = {}, pos + 1
    while true do
      local c = text:sub(i, i)
      if c == "" then error("unterminated string") end
      if c == '"' then pos = i + 1; return table.concat(out) end
      if c == "\\" then
        local e = text:sub(i + 1, i + 1)
        local map = { b = "\b", f = "\f", n = "\n", r = "\r", t = "\t" }
        if e == "u" then
          local code = tonumber(text:sub(i + 2, i + 5), 16)
          if code < 0x80 then out[#out + 1] = string.char(code)
          elseif code < 0x800 then
            out[#out + 1] = string.char(0xC0 | (code >> 6), 0x80 | (code & 0x3F))
          else
            out[#out + 1] = string.char(0xE0 | (code >> 12), 0x80 | ((code >> 6) & 0x3F),
              0x80 | (code & 0x3F))
          end
          i = i + 6
        else
          out[#out + 1] = map[e] or e
          i = i + 2
        end
      else
        out[#out + 1] = c
        i = i + 1
      end
    end
  end
  value = function()
    skip()
    local c = text:sub(pos, pos)
    if c == "{" then
      local obj = {}
      pos = pos + 1; skip()
      if text:sub(pos, pos) == "}" then pos = pos + 1; return obj end
      while true do
        skip()
        local key = str(); skip()
        pos = pos + 1 -- ':'
        obj[key] = value(); skip()
        local sep = text:sub(pos, pos); pos = pos + 1
        if sep == "}" then return obj end
      end
    elseif c == "[" then
      local arr = {}
      pos = pos + 1; skip()
      if text:sub(pos, pos) == "]" then pos = pos + 1; return arr end
      while true do
        arr[#arr + 1] = value(); skip()
        local sep = text:sub(pos, pos); pos = pos + 1
        if sep == "]" then return arr end
      end
    elseif c == '"' then
      return str()
    elseif text:sub(pos, pos + 3) == "true" then pos = pos + 4; return true
    elseif text:sub(pos, pos + 4) == "false" then pos = pos + 5; return false
    elseif text:sub(pos, pos + 3) == "null" then pos = pos + 4; return nil
    end
    local num = text:match("^-?%d+%.?%d*[eE]?[-+]?%d*", pos)
    if not num or num == "" then error("unexpected character at " .. pos) end
    pos = pos + #num
    return tonumber(num)
  end
  return value()
end

---------------------------------------------------------------------------
-- Engine discovery and HTTP through curl.exe
---------------------------------------------------------------------------

local function sep() return package.config:sub(1, 1) end

-- Engine data folders: COVER_MAKER_HOME, else the installed app's folder,
-- then a development build's (Cover_Maker.dev).
local function homes()
  local override = os.getenv("COVER_MAKER_HOME")
  if override and override ~= "" then return { override } end
  local base = (os.getenv("LOCALAPPDATA") or "") .. sep()
  return { base .. "Cover_Maker", base .. "Cover_Maker.dev" }
end

local function read_file(path)
  local f = io.open(path, "rb")
  if not f then return nil end
  local data = f:read("a")
  f:close()
  return data
end

local function write_file(path, data)
  local f = assert(io.open(path, "wb"))
  f:write(data)
  f:close()
end

local function read_discovery(home)
  local run = home .. sep() .. "run"
  local text = read_file(run .. sep() .. "engine.json")
  if not text then return nil end
  local ok, info = pcall(json.decode, text)
  if not ok or type(info) ~= "table" or not info.port or not info.token then return nil end
  info.run = run
  return info
end

local function curl_path()
  local root = os.getenv("SYSTEMROOT") or "C:\\Windows"
  return root .. "\\System32\\curl.exe"
end

local function quote(s) return '"' .. s .. '"' end

-- Calls the engine. The token goes through a header file in the user-only run
-- folder, never on the command line (other processes can read command lines).
local function request(engine, method, path, body)
  local id = tostring(math.random(1, 1e9))
  local headers = engine.run .. sep() .. "reaper-" .. id .. ".hdr"
  write_file(headers, "Authorization: Bearer " .. engine.token .. "\r\n"
    .. "Content-Type: application/json\r\n")
  local args = { quote(curl_path()), "-s", "-S", "--max-time", "60", "-X", method,
    "-H", quote("@" .. headers), "-w", quote("\\n%{http_code}") }
  local payload
  if body then
    payload = engine.run .. sep() .. "reaper-" .. id .. ".json"
    write_file(payload, json.encode(body))
    args[#args + 1] = "--data-binary"
    args[#args + 1] = quote("@" .. payload)
  end
  args[#args + 1] = quote(string.format("http://%s:%d%s", engine.host or "127.0.0.1",
    math.floor(engine.port), path))
  local out = reaper.ExecProcess(table.concat(args, " "), 70000) or ""
  os.remove(headers)
  if payload then os.remove(payload) end
  -- ExecProcess returns "<exit code>\n<stdout>"; curl appends "\n<status>".
  local code, rest = out:match("^(%-?%d+)\n(.*)$")
  if code ~= "0" or not rest then return nil, "curl failed: " .. out end
  local text, status = rest:match("^(.*)\n(%d+)%s*$")
  status = tonumber(status)
  local ok, data = pcall(json.decode, text ~= "" and text or "null")
  return status, ok and data or text
end

---------------------------------------------------------------------------
-- REAPER side
---------------------------------------------------------------------------

local function message(text) reaper.ShowMessageBox(text, SCRIPT, 0) end

-- The selected item's source file, its timeline position and the source
-- offset so the stems line up with what is heard.
local function selected_source()
  local item = reaper.GetSelectedMediaItem(0, 0)
  if not item then return nil end
  local take = reaper.GetActiveTake(item)
  if not take or reaper.TakeIsMIDI(take) then return nil end
  local source = reaper.GetMediaItemTake_Source(take)
  local parent = reaper.GetMediaSourceParent(source)
  while parent do source = parent; parent = reaper.GetMediaSourceParent(source) end
  local file = reaper.GetMediaSourceFileName(source, "")
  if not file or file == "" then return nil end
  return {
    file = file,
    position = reaper.GetMediaItemInfo_Value(item, "D_POSITION"),
    offset = reaper.GetMediaItemTakeInfo_Value(take, "D_STARTOFFS"),
    track = reaper.GetMediaItemTrack(item),
  }
end

local function split(csv)
  local out = {}
  for part in csv:gmatch("[^,]+") do
    local stem = part:lower():gsub("^%s+", ""):gsub("%s+$", "")
    out[#out + 1] = stem
  end
  return out
end

local function valid_stems(list)
  local known = {}
  for _, s in ipairs(STEMS) do known[s] = true end
  for _, s in ipairs(list) do
    if not known[s] then return false, s end
  end
  return #list > 0, nil
end

local function output_dir()
  local project = reaper.GetProjectPath("")
  return project .. sep() .. "Cover_Maker stems"
end

-- Output names in the order the stems were asked for, others after them.
local function ordered(outputs, wanted)
  local rank = {}
  for i, stem in ipairs(wanted or {}) do rank[stem:lower()] = i end
  local names = {}
  for name in pairs(outputs) do names[#names + 1] = name end
  table.sort(names, function(a, b)
    local ra, rb = rank[a:lower()] or math.huge, rank[b:lower()] or math.huge
    if ra ~= rb then return ra < rb end
    return a:lower() < b:lower()
  end)
  return names
end

local function insert_stems(outputs, placement, wanted)
  local names = ordered(outputs, wanted)
  if #names == 0 then return 0 end

  reaper.Undo_BeginBlock()
  reaper.PreventUIRefresh(1)
  local index = reaper.CountTracks(0)
  if placement.track then
    index = math.floor(reaper.GetMediaTrackInfo_Value(placement.track, "IP_TRACKNUMBER"))
  end
  local start = placement.position - placement.offset
  for i, name in ipairs(names) do
    reaper.InsertTrackAtIndex(index + i - 1, true)
    local track = reaper.GetTrack(0, index + i - 1)
    reaper.GetSetMediaTrackInfo_String(track, "P_NAME", name, true)
    local source = reaper.PCM_Source_CreateFromFile(outputs[name])
    local length = reaper.GetMediaSourceLength(source)
    local item = reaper.AddMediaItemToTrack(track)
    local take = reaper.AddTakeToMediaItem(item)
    reaper.SetMediaItemTake_Source(take, source)
    reaper.GetSetMediaItemTakeInfo_String(take, "P_NAME", name, true)
    -- The stems cover the whole song: place the song start where the source
    -- item's start would be, trimming the head if that is before 0.
    local head = math.max(-start, 0)
    reaper.SetMediaItemInfo_Value(item, "D_POSITION", math.max(start, 0))
    reaper.SetMediaItemTakeInfo_Value(take, "D_STARTOFFS", head)
    reaper.SetMediaItemInfo_Value(item, "D_LENGTH", math.max(length - head, 0))
  end
  reaper.PreventUIRefresh(-1)
  reaper.TrackList_AdjustWindows(false)
  reaper.UpdateArrange()
  reaper.Undo_EndBlock("Cover_Maker: insert stems", -1)
  return #names
end

local function wait_for(engine, job_id, placement, wanted)
  local last = 0
  local function poll()
    if reaper.time_precise() - last < POLL_SECONDS then
      reaper.defer(poll)
      return
    end
    last = reaper.time_precise()
    local status, job = request(engine, "GET", "/jobs/" .. math.floor(job_id))
    if status ~= 200 or type(job) ~= "table" then
      message("Lost contact with Cover_Maker: " .. tostring(job))
      return
    end
    if job.status == "done" or job.status == "failed" or job.status == "cancelled" then
      local item = job.item_list and job.item_list[1]
      if job.status ~= "done" or not item then
        message("The job did not finish: " .. tostring(job.error or (item and item.error) or job.status))
        return
      end
      local count = insert_stems(item.outputs or {}, placement, wanted)
      if count == 0 then message("The job finished without stem files.") end
      return
    end
    reaper.defer(poll)
  end
  reaper.defer(poll)
end

local function main()
  math.randomseed(math.floor(reaper.time_precise() * 1000))
  local engine, found
  for _, home in ipairs(homes()) do
    local info = read_discovery(home)
    if info then
      found = true
      if request(info, "GET", "/health") == 200 then engine = info; break end
    end
  end
  if not engine then
    message(found
      and "Cover_Maker is not answering (stale discovery file?). Restart the app and try again."
      or "Cover_Maker is not running. Open the Cover_Maker app and try again.")
    return
  end

  local source = selected_source()
  local default_input = source and source.file or ""
  local ok, values = reaper.GetUserInputs(SCRIPT, 3,
    "File or video link,Stems (" .. table.concat(STEMS, " ") .. "),I have the rights (y/n),extrawidth=300",
    default_input .. ",vocals,drums,bass,other,n")
  if not ok then return end
  -- GetUserInputs joins fields with commas: the stems field holds commas too.
  local fields = {}
  for part in (values .. ","):gmatch("([^,]*),") do fields[#fields + 1] = part end
  local input = fields[1]
  local rights = (fields[#fields] or ""):lower():sub(1, 1) == "y"
  local stems = split(table.concat(fields, ",", 2, #fields - 1))
  local good, bad = valid_stems(stems)
  if input == "" or not good then
    message(bad and ("Unknown stem: " .. bad) or "Give a file or link and at least one stem.")
    return
  end

  local placement = { position = reaper.GetCursorPosition(), offset = 0 }
  if source and input == source.file then placement = source end

  local body = {
    inputs = { input },
    stems = stems,
    mode = "extract",
    output_dir = output_dir(),
    rights_confirmed = rights,
  }
  local created_status, created = request(engine, "POST", "/jobs", body)
  if created_status ~= 201 or type(created) ~= "table" then
    local detail = type(created) == "table" and (created.detail or created.code) or tostring(created)
    if type(created) == "table" and created.code == "model_not_installed" then
      detail = "Install the required models in Cover_Maker first (" .. table.concat(created.models or {}, ", ") .. ")."
    elseif type(created) == "table" and created.code == "rights_required" then
      detail = "Links need you to confirm that you have the rights to the audio (answer y)."
    end
    message("Cover_Maker refused the job: " .. tostring(detail))
    return
  end
  wait_for(engine, created.job_id, placement, stems)
end

main()
