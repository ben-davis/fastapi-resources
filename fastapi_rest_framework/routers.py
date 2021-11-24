from fastapi import APIRouter

from fastapi_rest_framework.resources import SQLModelResource


class ResourceRouter(APIRouter):
    def __init__(
        self,
        *,
        resource: SQLModelResource,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)

        """
        TODO: Here is where we could build an instance
        of the resource class so that we can store things
        like self.request.
        """

        if resource.retrieve:
            self.get(
                f"/{{id}}",
                response_model=resource.RetrieveResponseModel,
                summary=f"Get {resource.name}",
            )(resource.retrieve)

        if resource.list:

            self.get(
                f"/",
                response_model=resource.ListResponseModel,
                summary=f"Get {resource.name} list",
            )(resource.list)

        if resource.create:
            self.post(
                f"/",
                response_model=resource.RetrieveResponseModel,
                summary=f"Create {resource.name}",
            )(resource.create)

        if resource.update:
            self.patch(
                f"/{{id}}",
                response_model=resource.RetrieveResponseModel,
                summary=f"Update {resource.name}",
            )(resource.update)

        if resource.delete:
            self.delete(f"/{{id}}", summary=f"Delete {resource.name}")(resource.delete)
