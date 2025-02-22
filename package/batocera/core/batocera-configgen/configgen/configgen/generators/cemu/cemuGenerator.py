#!/usr/bin/env python

from generators.Generator import Generator
import Command
import os
from os import path
from os import environ
import batoceraFiles
from xml.dom import minidom
import codecs
import controllersConfig
import shutil
import filecmp
import subprocess
from . import cemuControllers

from utils.logger import get_logger
eslog = get_logger(__name__)

cemuConfig  = batoceraFiles.CONF + '/cemu'
cemuRomdir = '/userdata/roms/wiiu'
cemuSaves = '/userdata/saves/wiiu'
cemuDatadir = '/usr/bin/cemu'

class CemuGenerator(Generator):

    def hasInternalMangoHUDCall(self):
        return True

    def generate(self, system, rom, playersControllers, guns, gameResolution):

        # in case of squashfs, the root directory is passed
        rpxrom = rom
        if os.path.isdir(rom + "/code"):
            rpxInDir = os.listdir(rom + "/code")
            for file in rpxInDir:
                basename, extension = os.path.splitext(file)
                if extension == ".rpx":
                    rpxrom = rom + "/code/" + basename + extension

        game_dir = cemuConfig + "/gameProfiles"
        resources_dir = cemuConfig + "/resources"
        cemu_exe = cemuConfig + "/cemu"
        if not path.isdir(batoceraFiles.BIOS + "/cemu"):
            os.mkdir(batoceraFiles.BIOS + "/cemu")
        if not path.isdir(cemuConfig):
            os.mkdir(cemuConfig)
        #graphic packs
        if not path.isdir(cemuSaves + "/graphicPacks"):
            os.mkdir(cemuSaves + "/graphicPacks")         
        if not os.path.exists(game_dir):
            shutil.copytree(cemuDatadir + "/gameProfiles", game_dir)
        if not os.path.exists(resources_dir):
            shutil.copytree(cemuDatadir + "/resources", resources_dir)

        for folder in ["controllerProfiles", "graphicPacks"]:
            if not path.isdir(cemuConfig + "/" + folder):
                os.mkdir(cemuConfig + "/" + folder)

        # Create save folder
        if not path.isdir(batoceraFiles.SAVES + "/cemu"):
            os.mkdir(batoceraFiles.SAVES + "/cemu")

        # Create the settings file
        CemuGenerator.CemuConfig(cemuConfig + "/settings.xml", system)
        
        # Copy the keys.txt file from where cemu reads it
        shutil.copyfile(batoceraFiles.BIOS + "/cemu/keys.txt", cemuConfig + "/keys.txt")
        
        # Set-up the controllers
        cemuControllers.generateControllerConfig(system, playersControllers)

        if rom == "config":
            commandArray = ["/usr/bin/cemu/cemu"]
        else:
            commandArray = ["/usr/bin/cemu/cemu", "-f", "-g", rpxrom]
        
        return Command.Command(
            array=commandArray,
            env={"XDG_CONFIG_HOME":batoceraFiles.CONF, "XDG_CACHE_HOME":batoceraFiles.CACHE,
                "XDG_DATA_HOME":batoceraFiles.SAVES,
                "SDL_GAMECONTROLLERCONFIG": controllersConfig.generateSdlGameControllerConfig(playersControllers),
                "SDL_JOYSTICK_HIDAPI": "0"
            })

    @staticmethod
    def CemuConfig(configFile, system):
        # Config file
        config = minidom.Document()
        if os.path.exists(configFile):
            try:
                config = minidom.parse(configFile)
            except:
                pass # reinit the file

        ## [ROOT]
        xml_root = CemuGenerator.getRoot(config, "content")
        # Default mlc path
        CemuGenerator.setSectionConfig(config, xml_root, "mlc_path", cemuSaves)
        # Remove auto updates
        CemuGenerator.setSectionConfig(config, xml_root, "check_update", "false")
        # Avoid the welcome window
        CemuGenerator.setSectionConfig(config, xml_root, "gp_download", "true")
        # Other options
        CemuGenerator.setSectionConfig(config, xml_root, "logflag", "0")
        CemuGenerator.setSectionConfig(config, xml_root, "advanced_ppc_logging", "false")
        CemuGenerator.setSectionConfig(config, xml_root, "use_discord_presence", "false")
        CemuGenerator.setSectionConfig(config, xml_root, "fullscreen_menubar", "false")
        CemuGenerator.setSectionConfig(config, xml_root, "vk_warning", "false")
        CemuGenerator.setSectionConfig(config, xml_root, "fullscreen", "true")
        # Language
        if not system.isOptSet("cemu_console_language") or system.config["cemu_console_language"] == "ui":
            lang = getLangFromEnvironment()
        else:
            lang = system.config["cemu_console_language"]
        CemuGenerator.setSectionConfig(config, xml_root, "cemu_console_language", str(getCemuLang(lang)))

        ## [WINDOW POSITION]
        CemuGenerator.setSectionConfig(config, xml_root, "window_position", "")
        window_position = CemuGenerator.getRoot(config, "window_position")
        # Default window position
        CemuGenerator.setSectionConfig(config, window_position, "x", "-4")
        # Default games path
        CemuGenerator.setSectionConfig(config, window_position, "y", "-23")

        ## [WINDOW SIZE]
        CemuGenerator.setSectionConfig(config, xml_root, "window_size", "")
        window_size = CemuGenerator.getRoot(config, "window_size")
        # Default window size
        CemuGenerator.setSectionConfig(config, window_size, "x", "640")
        # Default games path
        CemuGenerator.setSectionConfig(config, window_size, "y", "480")

        ## [GAME PATH]
        CemuGenerator.setSectionConfig(config, xml_root, "GamePaths", "")
        game_root = CemuGenerator.getRoot(config, "GamePaths")
        # Default games path
        CemuGenerator.setSectionConfig(config, game_root, "Entry", cemuRomdir)
     
        ## [GRAPHICS]
        CemuGenerator.setSectionConfig(config, xml_root, "Graphic", "")
        graphic_root = CemuGenerator.getRoot(config, "Graphic")
        # Graphical backend
        if system.isOptSet("cemu_gfxbackend"):
            CemuGenerator.setSectionConfig(config, graphic_root, "api", system.config["cemu_gfxbackend"])
        else:
            CemuGenerator.setSectionConfig(config, graphic_root, "api", "1") # Vulkan
        # Async VULKAN Shader compilation
        if system.isOptSet("cemu_async"):
            CemuGenerator.setSectionConfig(config, graphic_root, "AsyncCompile", system.config["cemu_async"]) 
        else:
            CemuGenerator.setSectionConfig(config, graphic_root, "AsyncCompile", "true")
        # Vsync
        if system.isOptSet("cemu_vsync"):
            CemuGenerator.setSectionConfig(config, graphic_root, "VSync", system.config["cemu_vsync"])
        else:
            CemuGenerator.setSectionConfig(config, graphic_root, "VSync", "0") # Off
        # Upscale Filter
        if system.isOptSet("cemu_upscale"):
            CemuGenerator.setSectionConfig(config, graphic_root, "UpscaleFilter", system.config["cemu_upscale"])
        else:
            CemuGenerator.setSectionConfig(config, graphic_root, "UpscaleFilter", "2") # Hermite
        # Downscale Filter
        if system.isOptSet("cemu_downscale"):
            CemuGenerator.setSectionConfig(config, graphic_root, "DownscaleFilter", system.config["cemu_downscale"])
        else:
            CemuGenerator.setSectionConfig(config, graphic_root, "DownscaleFilter", "0") # Bilinear
        # Aspect Ratio
        if system.isOptSet("cemu_aspect"):
            CemuGenerator.setSectionConfig(config, graphic_root, "FullscreenScaling", system.config["cemu_aspect"])
        else:
            CemuGenerator.setSectionConfig(config, graphic_root, "FullscreenScaling", "0") # Bilinear

        ## [GRAPHICS OVERLAY] - disabled for now
        CemuGenerator.setSectionConfig(config, graphic_root, "Overlay", "")
        overlay_root = CemuGenerator.getRoot(config, "Overlay")
        # Display FPS / CPU / GPU / RAM
        if system.isOptSet('showFPS') and system.getOptBoolean('showFPS') == True:
            CemuGenerator.setSectionConfig(config, overlay_root, "Position", "1")
            CemuGenerator.setSectionConfig(config, overlay_root, "FPS",       "true")
            CemuGenerator.setSectionConfig(config, overlay_root, "CPUUsage",  "true")
            CemuGenerator.setSectionConfig(config, overlay_root, "RAMUsage",  "true")
            CemuGenerator.setSectionConfig(config, overlay_root, "VRAMUsage", "true")
        else:
            CemuGenerator.setSectionConfig(config, overlay_root, "Position", "0")
            CemuGenerator.setSectionConfig(config, overlay_root, "FPS",       "false")
            CemuGenerator.setSectionConfig(config, overlay_root, "CPUUsage",  "false")
            CemuGenerator.setSectionConfig(config, overlay_root, "RAMUsage",  "false")
            CemuGenerator.setSectionConfig(config, overlay_root, "VRAMUsage", "false")

        ## [AUDIO]
        CemuGenerator.setSectionConfig(config, xml_root, "Audio", "")
        audio_root = CemuGenerator.getRoot(config, "Audio")
        # Use cubeb (curently the only option for linux)
        CemuGenerator.setSectionConfig(config, audio_root, "api", "3")
        # Turn audio ONLY on TV
        if system.isOptSet("cemu_audio_channels"):
            CemuGenerator.setSectionConfig(config, audio_root, "TVChannels", system.config["cemu_audio_channels"])
        else:
            CemuGenerator.setSectionConfig(config, audio_root, "TVChannels", "1") # Stereo
        # Set volume to the max
        CemuGenerator.setSectionConfig(config, audio_root, "TVVolume", "100")
        # Set the audio device - we choose the 1st device as this is more likely the answer
        # pactl list sinks-raw | sed -e s+"^sink=[0-9]* name=\([^ ]*\) .*"+"\1"+ | sed 1q | tr -d '\n'
        proc = subprocess.run(["/usr/bin/cemu/get-audio-device"], stdout=subprocess.PIPE)
        cemuAudioDevice = proc.stdout.decode('utf-8')
        eslog.debug("*** audio device = {} ***".format(cemuAudioDevice))
        if system.isOptSet("cemu_audio_config") and system.getOptBoolean("cemu_audio_config") == True:
            CemuGenerator.setSectionConfig(config, audio_root, "TVDevice", cemuAudioDevice)
        elif system.isOptSet("cemu_audio_config") and system.getOptBoolean("cemu_audio_config") == False:
            # don't change the config setting
            eslog.debug("*** use config audio device ***")
        else:
            CemuGenerator.setSectionConfig(config, audio_root, "TVDevice", cemuAudioDevice)
        
        # Save the config file
        xml = open(configFile, "w")

        # TODO: python 3 - workaround to encode files in utf-8
        xml = codecs.open(configFile, "w", "utf-8")
        dom_string = os.linesep.join([s for s in config.toprettyxml().splitlines() if s.strip()]) # remove ugly empty lines while minicom adds them...
        xml.write(dom_string)
    
    # Show mouse for touchscreen actions    
    def getMouseMode(self, config):
        if "cemu_touchpad" in config and config["cemu_touchpad"] == "True":
            return True
        else:
            return False

    @staticmethod
    def getRoot(config, name):
        xml_section = config.getElementsByTagName(name)

        if len(xml_section) == 0:
            xml_section = config.createElement(name)
            config.appendChild(xml_section)
        else:
            xml_section = xml_section[0]

        return xml_section

    @staticmethod
    def setSectionConfig(config, xml_section, name, value):
        xml_elt = xml_section.getElementsByTagName(name)
        if len(xml_elt) == 0:
            xml_elt = config.createElement(name)
            xml_section.appendChild(xml_elt)
        else:
            xml_elt = xml_elt[0]

        if xml_elt.hasChildNodes():
            xml_elt.firstChild.data = value
        else:
            xml_elt.appendChild(config.createTextNode(value))

# Language setting
def getLangFromEnvironment():
    if 'LANG' in environ:
        return environ['LANG'][:5]
    else:
        return "en_US"

def getCemuLang(lang):
    availableLanguages = { "ja_JP": 0, "en_US": 1, "fr_FR": 2, "de_DE": 3, "it_IT": 4, "es_ES": 5, "zh_CN": 6, "ko_KR": 7, "nl_NL": 8, "pt_PT": 9, "ru_RU": 10, "zh_TW": 11 }
    if lang in availableLanguages:
        return availableLanguages[lang]
    else:
        return availableLanguages["en_US"]
