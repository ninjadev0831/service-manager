import os
import requests
import time

from servicemanager.smfile import remove_if_exists
from .actions.colours import BColors
from .smnexus import SmNexus
from xml.dom.minidom import parseString
from servicemanager.smdownload import download, header

b = BColors()


class SmArtifactory:
    def __init__(self, context, service_name):
        self.context = context
        self.service_name = service_name
        self.service_type = context.service_type(service_name)

    def find_latest_in_dom(self, dom):
        try:
            data = dom.getElementsByTagName("versioning")[0]
        except:
            self.context.log("Unable to get latest version from artifactory")
            return None

        latest_snapshot = data.getElementsByTagName("latest")[0].firstChild
        latest_release = data.getElementsByTagName("release")

        if latest_snapshot.nodeValue == "999-SNAPSHOT" and latest_release and latest_release[0].firstChild is not None:
            return latest_release[0].firstChild.nodeValue
        else:
            return latest_snapshot.nodeValue

    def _find_all_versions_in_dom(self, dom):
        try:
            data = dom.getElementsByTagName("version")
        except:
            self.context.log("Unable to get all version from artifactory")
            return None

        versions = []
        for element in data:
            version = element.firstChild.nodeValue
            versions.append(version)
        return versions

    def _get_version_info_from_artifactory(self, artifact, repositoryId, groupId):
        url = (
            self.context.config_value("artifactory")["protocol"]
            + "://"
            + self.context.config_value("artifactory")["host"]
            + "/"
            + repositoryId
            + "/"
            + groupId
            + artifact
            + "/maven-metadata.xml"
        )

        self.context.log("Downloading metadata from Artifactory at %s" % url, True)

        body = ""
        for attempt_count in range(1, 6):
            try:
                response = requests.get(url)
                body = response.text
                response.close()
                break
            except Exception as error:
                self.context.log("Attempt number %d failed. Reason: %s" % (attempt_count, error))

                if attempt_count == 5:
                    self.context.log("Aborting download from Artifactory at %s" % url)
                    raise

                if attempt_count < 5:
                    time.sleep(1)

        dom = parseString(body)
        return dom

    def find_all_versions(self, run_from):
        binary = self.context.service_data(self.service_name)["binary"]
        repo_mappings = self.context.config_value("artifactory")["repoMappings"]
        dom = self._get_version_info_from_artifactory(binary["artifact"], repo_mappings[run_from], binary["groupId"])
        versions = self._find_all_versions_in_dom(dom)
        return versions

    def find_latest_version(self, run_from, artifact, groupId):
        version_env_var = None
        if "versionEnv" in self.context.service_data(self.service_name):
            version_env_var = self.context.service_data(self.service_name)["versionEnv"]

        try:
            version = os.environ[version_env_var]
        except Exception:
            repo_mappings = self.context.config_value("artifactory")["repoMappings"]
            version = self.find_latest_in_dom(
                self._get_version_info_from_artifactory(artifact, repo_mappings[run_from], groupId)
            )
        return version

    def _download_from_artifactory(self, artifactory_path, local_filename, repositoryId, show_progress):
        url = (
            self.context.config_value("artifactory")["protocol"]
            + "://"
            + self.context.config_value("artifactory")["host"]
            + "/"
            + repositoryId
            + "/"
            + artifactory_path
        )
        if show_progress:
            self.context.log("Downloading artefact from Artifactory at %s" % url, True)
        for attempt_count in range(1, 6):
            try:
                download(url, local_filename, show_progress)
                break
            except Exception as error:
                self.context.log("Attempt number %d failed. Reason: %s" % (attempt_count, error))

                if attempt_count == 5:
                    self.context.log("Aborting download from Artifactory at %s" % url)
                    raise

                if attempt_count < 5:
                    time.sleep(1)

    def _download_md5(self, artifactory_path, repositoryId):
        try:
            url = (
              self.context.config_value("artifactory")["protocol"]
              + "://"
              + self.context.config_value("artifactory")["host"]
              + "/"
              + repositoryId
              + "/"
              + artifactory_path
            )
            return header(url, "x-checksum-md5")
        except Exception as error:
            self.context.log("Failed to download md5 checksum from Artifactory at %s" % url)
            return ""

    def download_jar_if_necessary(self, run_from, version):
        binary_config = self.context.service_data(self.service_name)["binary"]
        artifact = binary_config["artifact"]
        groupId = binary_config["groupId"]
        repo_mappings = self.context.config_value("artifactory")["repoMappings"]
        repositoryId = repo_mappings[run_from]

        if not version:
            version = self.find_latest_version(run_from, artifact, groupId)

        if version:

            extension = "." + binary_config.get("ext", "tgz")
            localFilename = artifact + extension

            if self.service_type == "assets":
                localFilename = artifact + "-" + str(version) + extension

            artifactoryFilename = artifact + "-" + str(version) + extension
            artifactoryFilePath = groupId + artifact + "/" + str(version) + "/" + artifactoryFilename
            microservice_target_path = self.context.get_microservice_target_path(self.service_name)
            downloaded_artifact_path = microservice_target_path + localFilename

            # first download the md5 file in order to determine if new artifact download is required
            artifactory_md5 = self._download_md5(artifactoryFilePath, repositoryId)
            local_md5 = SmNexus._md5_if_exists(downloaded_artifact_path)

            if local_md5 != artifactory_md5:
                remove_if_exists(downloaded_artifact_path)
                self.context.log(
                    "Downloading Artifactory binary for '" + self.service_name + "': " + artifactoryFilename, True,
                )
                self._download_from_artifactory(
                    artifactoryFilePath, downloaded_artifact_path, repositoryId, self.context.show_progress,
                )
            else:
                self.context.log(
                    "Skipped download of %s. The local copy matches the one on Artifactory" % artifactoryFilename, True,
                )
            return artifactoryFilename
        else:
            print(
                b.warning
                + "WARNING: Due to lack of version data from Artifactory you may not have an up to date version..."
                + b.endc
            )
