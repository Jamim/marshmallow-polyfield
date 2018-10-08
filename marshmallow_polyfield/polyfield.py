from marshmallow import ValidationError
from marshmallow import Schema
from marshmallow.fields import Field

try:
    # UnmarshalResult not present in >=3.0.0, so use to flag marshmallow version
    from marshmallow import UnmarshalResult  # NOQA
    MARSHMALLOW_3 = False
except ImportError:
    MARSHMALLOW_3 = True


class PolyField(Field):
    """
    A field that (de)serializes to one of many types. Passed in functions
    are called to disambiguate what schema to use for the (de)serialization
    Intended to assist in working with fields that can contain any subclass
    of a base type
    """
    def __init__(
            self,
            serialization_schema_selector=None,
            deserialization_schema_selector=None,
            many=False,
            **metadata
    ):
        """
        :param serialization_schema_selector: Function that takes in either
        an object representing that object, it's parent object
        and returns the appropriate schema.
        :param deserialization_schema_selector: Function that takes in either
        an a dict representing that object, dict representing it's parent dict
        and returns the appropriate schema

        """
        super(PolyField, self).__init__(**metadata)
        self.many = many
        self.serialization_schema_selector = serialization_schema_selector
        self.deserialization_schema_selector = deserialization_schema_selector

    def _deserialize(self, value, attr, data):
        if not self.many:
            value = [value]

        results = []
        for v in value:
            deserializer = None
            try:
                deserializer = self.deserialization_schema_selector(v, data)
                if isinstance(deserializer, type):
                    deserializer = deserializer()
                if not isinstance(deserializer, (Field, Schema)):
                    raise TypeError('Invalid deserializer type')
            except Exception:
                class_type = None
                if deserializer:
                    class_type = str(type(deserializer))

                raise ValidationError(
                    "Unable to use schema. Ensure there is a deserialization_schema_selector"
                    " and that it returns a field or a schema when the function is passed in "
                    "{value_passed}. This is the class I got. "
                    "Make sure it is a field or a schema: {class_type}".format(
                        value_passed=v,
                        class_type=class_type
                    )
                )

            # Will raise ValidationError if any problems
            if hasattr(deserializer, 'context'):
                deserializer.context.update(getattr(self, 'context', {}))
            if isinstance(deserializer, Field):
                data = deserializer.deserialize(v, attr, data)
            else:
                load_result = deserializer.load(v)
                if MARSHMALLOW_3:
                    data = load_result
                else:
                    data, errors = load_result

                    if errors:
                        raise ValidationError(errors)

            results.append(data)

        if self.many:
            return results
        else:
            # Will be at least one otherwise value would have been None
            return results[0]

    def _serialize(self, value, key, obj):
        if value is None:
            return None
        try:
            if self.many:
                res = []
                for v in value:
                    schema = self.serialization_schema_selector(v, obj)
                    schema.context.update(getattr(self, 'context', {}))

                    dump_result = schema.dump(v)

                    if MARSHMALLOW_3:
                        res.append(dump_result)
                    else:
                        res.append(dump_result.data)
                return res
            else:
                schema = self.serialization_schema_selector(value, obj)
                schema.context.update(getattr(self, 'context', {}))
                dump_result = schema.dump(value)
                if MARSHMALLOW_3:
                    return dump_result
                else:
                    return dump_result.data
        except Exception as err:
            raise TypeError(
                'Failed to serialize object. Error: {0}\n'
                ' Ensure the serialization_schema_selector exists and '
                ' returns a Schema and that schema'
                ' can serialize this value {1}'.format(err, value))
