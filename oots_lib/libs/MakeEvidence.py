import base64
import logging
import os
from dataclasses import is_dataclass

from pyRegRep4 import deep_get
from pyRegRep4.RIMParsing import Parsing

from oots_lib.import_env import import_env
from oots_lib.lib.EvidanceMetadata import (
    Distribution,
    EMetadata,
    IsAbout,
    IsConformantTo,
    IssuingAuthority,
)
from oots_lib.lib.exception import EDMException
from oots_lib.lib.toLogger import ToLogger
from oots_lib.lib.UseRedis import UseRedisAsync as Redis
from oots_lib.models.Base import MainBase
from oots_lib.models.Person import Person, get_person_from_redis
from oots_lib.models.RequestEDM import get_edm_request_from_redis
from oots_lib.models.ResponseEvidences import (
    Classification,
    Evidences,
    ExtrinsicObjectType,
    RegistryPackageType,
    RepositoryItemRef,
    save_evidences_to_redis,
)
from oots_lib.redis_keys import Keys

_logger = logging.getLogger(__name__)

KEYS = Keys()
QUEUE_OUTCOMING = import_env("QUEUE_OUTCOMING")
IF_PREVIEW: bool = import_env("IF_PREVIEW").lower() == 'true'


class MakeEvidence:
    ISSUING_AUTHORITY_ID = ""
    ISSUING_AUTHORITY_SCHEME = ""
    ISSUING_AUTHORITY_NAME = ""
    CONFORMANT_TO_URL = ''

    def __init__(self, message_id: str, redis: Redis):
        super().__init__()

        self.message_id = message_id
        self.redis = redis

        self.person: Person | None = None
        self.request: Parsing | None = None
        self.as4: dict | None | None = None

        self.log: ToLogger | None | None = None
        self.evidence: Evidences | None = None
        self._request_content_type: str | None = None

        self.request_to_service: dict | None = None

        self.response_from_service = None
        self.data: MainBase | None = None
        self.title = ""
        self.description: list[str] = []

    @property
    def if_preview(self):
        _logger.debug(f"Перевірка прапора preview для повідомлення {self.message_id}")

        if self.request is None:
            raise ValueError(
                f"Запит для повідомлення {self.message_id} не зчитаний: спершу викличте read_data()"
            )

        request: dict = self.request.serialize()
        preview: bool = deep_get(request, 'doc', 'PossibilityForPreview', default=False)

        _logger.debug(f"Значення прапора preview у запиті: {preview}")
        _logger.debug(f"Прапор preview встановлено, використовуємо глобальне налаштування IF_PREVIEW: {IF_PREVIEW}")

        pr = False if not preview and not IF_PREVIEW else True

        _logger.debug(f"Результат перевірки прапора preview для повідомлення {self.message_id}: {pr}")
        return pr

    async def read_data(self):
        """Зчитує вхідні дані повідомлення з Redis.

        Raises:
            EDMException: Якщо запит EDM або дані особи відсутні у Redis
        """
        request_key = KEYS.get_request_edm(self.message_id)
        request = await get_edm_request_from_redis(self.redis, request_key)
        if request is None:
            raise self._not_found(
                message="Запит EDM не знайдено",
                detail=f"У Redis відсутній запит EDM за ключем {request_key}",
            )
        self.request = Parsing(request.content)

        person_key = KEYS.get_request_person(self.message_id)
        self.person = await get_person_from_redis(self.redis, person_key)
        if self.person is None:
            raise self._not_found(
                message="Інформацію про людину не знайдено",
                detail=f"У Redis відсутні дані особи за ключем {person_key}",
            )

        self.as4 = await self.redis.get_from_redis(KEYS.get_request_as4(self.message_id))

    def _not_found(self, message: str, detail: str) -> EDMException:
        return EDMException(
            redis=self.redis,
            queue=None,
            key=None,
            message_id=str(self.message_id),
            code="EDM:ERR:0004",
            message=message,
            detail=detail,
        )

    async def load_data_to_redis(self):
        """
        Зберігає сформовані докази до Redis у форматі Evidences.

        Після збереження перевіряє preview-прапор через get_flag()
        і за потреби відправляє повідомлення на обробку.
        """
        _logger.info(f"Збереження набору доказів для повідомлення {self.message_id}")

        if is_dataclass(self.evidence):
            await save_evidences_to_redis(self.redis, KEYS.get_response_evidence(self.message_id), self.evidence)
        else:
            raise TypeError(f"Очікувався Evidences, отримано {type(self.evidence)}")

        # Перевіряємо, чи потрібно відправляти на обробку
        if not self.if_preview:
            _logger.info(f"Відправляємо повідомлення {self.message_id} до черги обробки")
            await self.redis.push_to_queue(QUEUE_OUTCOMING, f"{self.message_id}")
        else:
            _logger.debug(f"Повідомлення {self.message_id} потребує preview, обробка відкладена")

    def generate_metadata(self, main_evidence: bool = True):
        if self.person is None:
            raise ValueError(
                f"Дані особи для повідомлення {self.message_id} не зчитані: спершу викличте read_data()"
            )
        person_tree = self.person.xml_tree
        if person_tree is None:
            raise ValueError(
                f"XML особи для повідомлення {self.message_id} не сформовано"
            )

        distribution = Distribution(self.request_content_type)
        conformantTo = IsConformantTo(self.CONFORMANT_TO_URL)     # NOSONAR
        usingAuthority = IssuingAuthority(self.ISSUING_AUTHORITY_SCHEME, self.ISSUING_AUTHORITY_ID)     # NOSONAR
        usingAuthority.name(lang='UA', name=self.ISSUING_AUTHORITY_NAME)
        about = IsAbout(person_tree)

        metadata = EMetadata()

        if main_evidence:
            about_tree = about.xml_tree
            conformant_tree = conformantTo.xml_tree
            distribution_tree = distribution.xml_tree
            authority_tree = usingAuthority.xml_tree
            assert about_tree is not None
            assert conformant_tree is not None
            assert distribution_tree is not None
            assert authority_tree is not None
            metadata.isAbout(about_tree)
            metadata.isConformeant(conformant_tree)
            metadata.distribution(distribution_tree)
            metadata.issuingAuthority(authority_tree)
        else:
            ...

        return metadata.xml_string

    @property
    def request_content_type(self):
        if self.request is None:
            raise ValueError("Запит не ініціалізовано")
        if self._request_content_type is None:
            self._request_content_type = deep_get(
                self.request.serialize(any_type=True),
                'query',
                'EvidenceRequest',
                'sdg:DataServiceEvidenceType',
                'sdg:DistributedAs',
                'sdg:Format'
            )
        return self._request_content_type

    async def transform_data(self):

        if self.data is None:
            raise ValueError(
                f"Джерело даних для повідомлення {self.message_id} не встановлено: "
                "задайте self.data перед transform_data()"
            )

        try:
            documents = await self.data.generate_data()
        except Exception as e:
            raise self._not_found(
                message="Інформацію про людину не знайдено",
                detail=str(e),
            ) from e

        content_type = self.request_content_type
        _logger.info(f"Тип контенту: {content_type}")

        if not content_type:
            _logger.error("Тип контенту у запиті не вказаний")
            raise EDMException(
                redis=self.redis,
                queue=None,
                key=None,
                message_id=str(self.message_id),
                code="EDM:ERR:0003",
                message="Тип контенту у запиті не вказаний",
                detail="У запиті відсутній sdg:DistributedAs/sdg:Format",
            )

        evidences = []

        for doc in documents:

            contents = []
            extrinsic = ExtrinsicObjectType(
                classification=Classification(classificationNode='MainEvidence'),
                EvidenceMetadata=self.generate_metadata(main_evidence=True),
                RepositoryItemRef=RepositoryItemRef(title="Cerificate of Marriage"),
            )

            if 'pdf' in content_type:
                _logger.debug("Перетворення документу у PDF")
                pdf = doc.get_pdf()
                extrinsic.content_type = "application/pdf"
                extrinsic.encoding = 'base64'
                extrinsic.content = base64.b64encode(pdf).decode("utf-8")
                contents.append(extrinsic)

            elif 'xml' in content_type:
                _logger.debug("Перетворення документу у XML")
                extrinsic.content_type = "application/xml"
                extrinsic.content = doc.get_xml()
                contents.append(extrinsic)

            elif 'json' in content_type:
                _logger.debug("Перетворення документу у JSON")
                extrinsic.content_type = "application/json"
                extrinsic.content = doc.get_json()
                contents.append(extrinsic)

            else:
                _logger.error(f"Невідомий тип контенту: {content_type}")
                raise EDMException(
                    redis=self.redis,
                    queue=None,
                    key=None,
                    message_id=str(self.message_id),
                    code="EDM:ERR:0006",
                    message="Невідомий тип контенту",
                    detail=f"Невідомий тип контенту: {content_type}",
                )
            _logger.debug(f"Створено ExtrinsicObjectType: {extrinsic}")
            # додати інші представлення до contents
            ...
            _logger.debug('Додали всі представлення доказу')

            _logger.debug(f"Створюємо RegistryPackageType для документа: {doc}")
            evidences.append(RegistryPackageType(RegistryPackage=contents))

        _logger.debug(f"Створено всі RegistryPackageType для документів, кількість: {len(evidences)}")
        evidence = Evidences(
            title=self.title,
            PreviewDescription=self.description,
            preview=self.if_preview,
            evidences=evidences,
        )
        _logger.debug(f'Створили Evidence: {evidence}')
        self.evidence = evidence
