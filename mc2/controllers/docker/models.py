from django.db import models
from mc2.controllers.base.models import Controller, EnvVariable, MarathonLabel
from django.conf import settings


class DockerController(Controller):
    docker_image = models.CharField(max_length=256)
    marathon_health_check_path = models.CharField(
        max_length=255, blank=True, null=True)
    port = models.PositiveIntegerField(default=0)
    domain_urls = models.TextField(max_length=8000, default="")
    volume_needed = models.BooleanField(default=False)
    volume_path = models.CharField(max_length=255, blank=True, null=True)

    def get_marathon_app_data(self):
        app_data = super(DockerController, self).get_marathon_app_data()
        docker_dict = {
            "image": self.docker_image,
            "forcePullImage": True,
            "network": "BRIDGE",
        }

        if self.port:
            docker_dict.update({
                "portMappings": [{"containerPort": self.port, "hostPort": 0}]
            })

        parameters_dict = []
        if self.volume_needed:
            parameters_dict.append({"key": "volume-driver", "value": "xylem"})
            parameters_dict.append({
                "key": "volume",
                "value": "%(app_id)s_media:%(path)s" % {
                    'app_id': self.app_id,
                    'path':
                        self.volume_path or
                        settings.MARATHON_DEFAULT_VOLUME_PATH}})

        if parameters_dict:
            docker_dict.update({"parameters": parameters_dict})

        domains = "%(generic_domain)s %(custom)s" % {
            'generic_domain': self.get_generic_domain(),
            'custom': self.domain_urls
        }

        service_labels = {
            "domain": domains.strip(),
            "name": self.name,
        }

        # Update custom labels
        if self.label_variables.exists():
            for label in self.label_variables.all():
                service_labels[label.name] = label.value

        app_data.update({
            "labels": service_labels,
            "container": {
                "type": "DOCKER",
                "docker": docker_dict
            }
        })

        if self.marathon_health_check_path:
            app_data.update({
                "ports": [0],
                "healthChecks": [{
                    "gracePeriodSeconds": 3,
                    "intervalSeconds": 10,
                    "maxConsecutiveFailures": 3,
                    "path": self.marathon_health_check_path,
                    "portIndex": 0,
                    "protocol": "HTTP",
                    "timeoutSeconds": 5
                }]
            })

        return app_data

    @classmethod
    def from_marathon_app_data(cls, owner, app_data):
        """
        Create a new model from the given Marathon app data.

        NOTE: This is tested with the output of `get_marathon_app_data()`
        above, so it may not correctly handle arbitrary fields.
        """
        docker_dict = app_data["container"]["docker"]
        args = {
            "slug": app_data["id"],
            "marathon_cpus": app_data["cpus"],
            "marathon_mem": app_data["mem"],
            "marathon_instances": app_data["instances"],
            "marathon_cmd": app_data.get("cmd", ""),
            "docker_image": docker_dict["image"],
        }

        if docker_dict.get("portMappings"):
            args["port"] = docker_dict["portMappings"][0]["containerPort"]

        for param in docker_dict.get("parameters", []):
            if param["key"] == "volume":
                args["volume_needed"] = True
                args["volume_path"] = param["value"].split(":", 1)[1]

        labels = []

        gen_domain = (u"%s.%s" % (app_data["id"], settings.HUB_DOMAIN)).strip()
        for k, v in app_data["labels"].items():
            if k == "name":
                args["name"] = v
            elif k == "domain":
                args["domain_urls"] = u" ".join(
                    [d for d in v.split(u" ") if d != gen_domain])
            else:
                labels.append({"name": k, "value": v})

        if "healthChecks" in app_data:
            hcp = app_data["healthChecks"][0]["path"]
            args["marathon_health_check_path"] = hcp

        self = cls.objects.create(owner=owner, **args)

        for label in labels:
            MarathonLabel.objects.create(controller=self, **label)

        for key, value in app_data.get("env", {}).items():
            EnvVariable.objects.create(controller=self, key=key, value=value)

        return self

    def to_dict(self):
        data = super(DockerController, self).to_dict()
        data.update({
            'port': self.port,
            'marathon_health_check_path': self.marathon_health_check_path
        })
        return data

    def get_generic_domain(self):
        return '%(app_id)s.%(hub)s' % {
            'app_id': self.app_id,
            'hub': settings.HUB_DOMAIN
        }
