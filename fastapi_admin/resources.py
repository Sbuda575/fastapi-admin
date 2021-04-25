from typing import List, Optional, Type, Union

from tortoise import ForeignKeyFieldInstance
from tortoise import Model as TortoiseModel
from tortoise.fields import BooleanField, DateField, DatetimeField, JSONField
from tortoise.fields.data import CharEnumFieldInstance, IntEnumFieldInstance, IntField, TextField

from fastapi_admin.exceptions import NoSuchFieldFound
from fastapi_admin.widgets import Widget, displays, inputs
from fastapi_admin.widgets.filters import Filter


class Resource:
    """
    Base Resource
    """

    label: str
    icon: str = ""


class Link(Resource):
    url: str
    target: str = "_self"
    page_pre_title: Optional[str] = None
    page_title: Optional[str] = None


class Field:
    name: str
    label: str
    display: displays.Display
    input: inputs.Input

    def __init__(
        self,
        name: str,
        label: str,
        display: Optional[displays.Display] = None,
        input_: Optional[Widget] = None,
    ):
        self.name = name
        self.label = label
        if not display:
            display = displays.Display()
        display.context.update(label=label)
        self.display = display
        if not input_:
            input_ = inputs.Input()
        input_.context.update(label=label, name=name)
        self.input = input_


class Model(Resource):
    model: Type[TortoiseModel]
    fields: List[Union[str, Field]] = []
    page_size: int = 10
    page_pre_title: Optional[str] = None
    page_title: Optional[str] = None
    filters: Optional[List[Union[str, Filter]]] = []
    can_edit: bool = True
    can_delete: bool = True
    can_create: bool = True
    enctype = "application/x-www-form-urlencoded"

    @classmethod
    async def get_inputs(cls, obj: Optional[TortoiseModel] = None):
        ret = []
        for field in cls.get_fields(is_display=False):
            input_ = field.input
            if isinstance(input_, inputs.DisplayOnly):
                continue
            if isinstance(input_, inputs.File):
                cls.enctype = "multipart/form-data"
            name = input_.context.get("name")
            ret.append(await input_.render(getattr(obj, name, None)))
        return ret

    @classmethod
    async def resolve_query_params(cls, values: dict):
        ret = {}
        for f in cls.filters:
            name = f.context.get("name")
            v = values.get(name)
            if v is not None and v != "":
                ret[name] = await f.parse_value(v)
        return ret

    @classmethod
    async def resolve_data(cls, data: dict):
        ret = {}
        for field in cls.get_fields(is_display=False):
            input_ = field.input
            if input_.context.get("disabled") or isinstance(input_, inputs.DisplayOnly):
                continue
            name = input_.context.get("name")
            v = data.get(name)
            ret[name] = await input_.parse_value(v)
        return ret

    @classmethod
    async def get_filters(cls, values: Optional[dict] = None):
        if not values:
            values = {}
        ret = []
        for f in cls.filters:
            name = f.context.get("name")
            value = values.get(name)
            ret.append(await f.render(value))
        return ret

    @classmethod
    def _get_fields_attr(cls, attr: str, display: bool = True):
        ret = []
        for field in cls.get_fields():
            if display and isinstance(field.display, displays.InputOnly):
                continue
            ret.append(getattr(field, attr))
        return ret or cls.model._meta.db_fields

    @classmethod
    def get_fields_name(cls, display: bool = True):
        return cls._get_fields_attr("name", display)

    @classmethod
    def _get_display_input_field(cls, field_name: str) -> Field:
        fields_map = cls.model._meta.fields_map
        field = fields_map.get(field_name)
        if not field:
            raise NoSuchFieldFound(f"Can't found field '{field}' in model {cls.model}")
        label = field_name
        null = field.null
        placeholder = field.description or ""
        display, input_ = displays.Display(), inputs.Input(
            placeholder=placeholder, null=null, default=field.default
        )
        if field.pk or field.generated:
            display, input_ = displays.Display(), inputs.DisplayOnly()
        elif isinstance(field, BooleanField):
            display, input_ = displays.Boolean(), inputs.Switch(null=null, default=field.default)
        elif isinstance(field, DatetimeField):
            if field.auto_now or field.auto_now_add:
                input_ = inputs.DisplayOnly()
            else:
                input_ = inputs.DateTime(null=null, default=field.default)
            display, input_ = displays.DatetimeDisplay(), input_
        elif isinstance(field, DateField):
            display, input_ = displays.DateDisplay(), inputs.Date(null=null, default=field.default)
        elif isinstance(field, IntEnumFieldInstance):
            display, input_ = displays.Display(), inputs.Enum(
                field.enum_type, null=null, default=field.default
            )
        elif isinstance(field, CharEnumFieldInstance):
            display, input_ = displays.Display(), inputs.Enum(
                field.enum_type, enum_type=str, null=null, default=field.default
            )
        elif isinstance(field, JSONField):
            display, input_ = displays.Json(), inputs.Json(null=null)
        elif isinstance(field, TextField):
            display, input_ = displays.Display(), inputs.TextArea(
                placeholder=placeholder, null=null, default=field.default
            )
        elif isinstance(field, IntField):
            display, input_ = displays.Display(), inputs.Number(
                placeholder=placeholder, null=null, default=field.default
            )
        elif isinstance(field, ForeignKeyFieldInstance):
            display, input_ = displays.Display(), inputs.ForeignKey(
                field.related_model, null=null, default=field.default
            )
            field_name = field.source_field

        return Field(name=field_name, label=label.title(), display=display, input_=input_)

    @classmethod
    def get_fields(cls, is_display: bool = True):
        ret = []
        for field in cls.fields or cls.model._meta.db_fields:
            if isinstance(field, str):
                field = cls._get_display_input_field(field)
                ret.append(field)
            else:
                if (is_display and isinstance(field.display, displays.InputOnly)) or (
                    not is_display and isinstance(field.input, inputs.DisplayOnly)
                ):
                    continue
                ret.append(field)
        return ret

    @classmethod
    def get_fields_label(cls, display: bool = True):
        return cls._get_fields_attr("label", display)


class Dropdown(Resource):
    resources: List[Type[Resource]]