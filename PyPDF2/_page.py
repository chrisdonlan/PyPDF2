# Copyright (c) 2006, Mathieu Fenniak
# Copyright (c) 2007, Ashish Kulkarni <kulkarni.ashish@gmail.com>
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
# * Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
# * The name of the author may not be used to endorse or promote products
# derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import math
import uuid
import warnings
from decimal import Decimal
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    Optional,
    Tuple,
    Union,
    cast,
)

from ._utils import (
    DEPR_MSG,
    DEPR_MSG_NO_REPLACEMENT,
    CompressedTransformationMatrix,
    TransformationMatrixType,
    b_,
    matrix_multiply,
)
from .constants import PageAttributes as PG
from .constants import Ressources as RES
from .errors import PageSizeNotDefinedError
from .generic import (
    ArrayObject,
    ContentStream,
    DictionaryObject,
    FloatObject,
    IndirectObject,
    NameObject,
    NullObject,
    NumberObject,
    RectangleObject,
    TextStringObject,
)


def _get_rectangle(self: Any, name: str, defaults: Iterable[str]) -> RectangleObject:
    retval: Union[None, RectangleObject, IndirectObject] = self.get(name)
    if isinstance(retval, RectangleObject):
        return retval
    if retval is None:
        for d in defaults:
            retval = self.get(d)
            if retval is not None:
                break
    if isinstance(retval, IndirectObject):
        retval = self.pdf.get_object(retval)
    retval = RectangleObject(retval)  # type: ignore
    _set_rectangle(self, name, retval)
    return retval


def getRectangle(self: Any, name: str, defaults: Iterable[str]) -> RectangleObject:
    warnings.warn(
        DEPR_MSG_NO_REPLACEMENT.format("getRectangle"),
        PendingDeprecationWarning,
        stacklevel=2,
    )
    return _get_rectangle(self, name, defaults)


def _set_rectangle(self: Any, name: str, value: Union[RectangleObject, float]) -> None:
    if not isinstance(name, NameObject):
        name = NameObject(name)
    self[name] = value


def setRectangle(self: Any, name: str, value: Union[RectangleObject, float]) -> None:
    warnings.warn(
        DEPR_MSG_NO_REPLACEMENT.format("setRectangle"),
        PendingDeprecationWarning,
        stacklevel=2,
    )
    _set_rectangle(self, name, value)


def _delete_rectangle(self: Any, name: str) -> None:
    del self[name]


def deleteRectangle(self: Any, name: str) -> None:
    warnings.warn(
        DEPR_MSG_NO_REPLACEMENT.format("deleteRectangle"),
        PendingDeprecationWarning,
        stacklevel=2,
    )
    del self[name]


def _create_rectangle_accessor(name: str, fallback: Iterable[str]) -> property:
    return property(
        lambda self: _get_rectangle(self, name, fallback),
        lambda self, value: _set_rectangle(self, name, value),
        lambda self: _delete_rectangle(self, name),
    )


def createRectangleAccessor(name: str, fallback: Iterable[str]) -> property:
    warnings.warn(
        DEPR_MSG_NO_REPLACEMENT.format("createRectangleAccessor"),
        PendingDeprecationWarning,
        stacklevel=2,
    )
    return _create_rectangle_accessor(name, fallback)


class Transformation:
    """
    Specify a 2D transformation.

    The transformation between two coordinate systems is represented by a 3-by-3
    transformation matrix written as follows::

        a b 0
        c d 0
        e f 1

    Because a transformation matrix has only six elements that can be changed,
    it is usually specified in PDF as the six-element array [ a b c d e f ].

    Coordinate transformations are expressed as matrix multiplications::

                                 a b 0
     [ x′ y′ 1 ] = [ x y 1 ] ×   c d 0
                                 e f 1


    Usage
    -----

        >>> from PyPDF2 import Transformation
        >>> op = Transformation().scale(sx=2, sy=3).translate(tx=10, ty=20)
        >>> page.add_transformation(op)
    """

    # 9.5.4 Coordinate Systems for 3D
    # 4.2.2 Common Transformations
    def __init__(self, ctm: CompressedTransformationMatrix = (1, 0, 0, 1, 0, 0)):
        self.ctm = ctm

    @property
    def matrix(self) -> TransformationMatrixType:
        return (
            (self.ctm[0], self.ctm[1], 0),
            (self.ctm[2], self.ctm[3], 0),
            (self.ctm[4], self.ctm[5], 1),
        )

    @staticmethod
    def compress(matrix: TransformationMatrixType) -> CompressedTransformationMatrix:
        return (
            matrix[0][0],
            matrix[0][1],
            matrix[1][0],
            matrix[1][1],
            matrix[0][2],
            matrix[1][2],
        )

    def translate(self, tx: float = 0, ty: float = 0) -> "Transformation":
        m = self.ctm
        return Transformation(ctm=(m[0], m[1], m[2], m[3], m[4] + tx, m[5] + ty))

    def scale(
        self, sx: Optional[float] = None, sy: Optional[float] = None
    ) -> "Transformation":
        if sx is None and sy is None:
            raise ValueError("Either sx or sy must be specified")
        if sx is None:
            sx = sy
        if sy is None:
            sy = sx
        assert sx is not None
        assert sy is not None
        op: TransformationMatrixType = ((sx, 0, 0), (0, sy, 0), (0, 0, 1))
        ctm = Transformation.compress(matrix_multiply(self.matrix, op))
        return Transformation(ctm)

    def rotate(self, rotation: float) -> "Transformation":
        rotation = math.radians(rotation)
        op: TransformationMatrixType = (
            (math.cos(rotation), math.sin(rotation), 0),
            (-math.sin(rotation), math.cos(rotation), 0),
            (0, 0, 1),
        )
        ctm = Transformation.compress(matrix_multiply(self.matrix, op))
        return Transformation(ctm)

    def __repr__(self) -> str:
        return f"Transformation(ctm={self.ctm})"


class PageObject(DictionaryObject):
    """
    PageObject represents a single page within a PDF file.

    Typically this object will be created by accessing the
    :meth:`get_page()<PyPDF2.PdfReader.get_page>` method of the
    :class:`PdfReader<PyPDF2.PdfReader>` class, but it is
    also possible to create an empty page with the
    :meth:`create_blank_page()<PyPDF2._page.PageObject.create_blank_page>` static method.

    :param pdf: PDF file the page belongs to.
    :param indirect_ref: Stores the original indirect reference to
        this object in its source PDF
    """

    def __init__(
        self,
        pdf: Optional[Any] = None,  # PdfReader
        indirect_ref: Optional[IndirectObject] = None,
    ) -> None:
        from ._reader import PdfReader

        DictionaryObject.__init__(self)
        self.pdf: Optional[PdfReader] = pdf
        self.indirect_ref = indirect_ref

    @staticmethod
    def create_blank_page(
        pdf: Optional[Any] = None,  # PdfReader
        width: Union[float, Decimal, None] = None,
        height: Union[float, Decimal, None] = None,
    ) -> "PageObject":
        """
        Return a new blank page.

        If ``width`` or ``height`` is ``None``, try to get the page size
        from the last page of *pdf*.

        :param pdf: PDF file the page belongs to
        :param float width: The width of the new page expressed in default user
            space units.
        :param float height: The height of the new page expressed in default user
            space units.
        :return: the new blank page:
        :rtype: :class:`PageObject<PageObject>`
        :raises PageSizeNotDefinedError: if ``pdf`` is ``None`` or contains
            no page
        """
        page = PageObject(pdf)

        # Creates a new page (cf PDF Reference  7.7.3.3)
        page.__setitem__(NameObject(PG.TYPE), NameObject("/Page"))
        page.__setitem__(NameObject(PG.PARENT), NullObject())
        page.__setitem__(NameObject(PG.RESOURCES), DictionaryObject())
        if width is None or height is None:
            if pdf is not None and len(pdf.pages) > 0:
                lastpage = pdf.pages[len(pdf.pages) - 1]
                width = lastpage.mediabox.width
                height = lastpage.mediabox.height
            else:
                raise PageSizeNotDefinedError()
        page.__setitem__(
            NameObject(PG.MEDIABOX), RectangleObject((0, 0, width, height))  # type: ignore
        )

        return page

    @staticmethod
    def createBlankPage(
        pdf: Optional[Any] = None,  # PdfReader
        width: Union[float, Decimal, None] = None,
        height: Union[float, Decimal, None] = None,
    ) -> "PageObject":
        """
        .. deprecated:: 1.28.0

            Use :meth:`create_blank_page` instead.
        """
        warnings.warn(
            DEPR_MSG.format("createBlankPage", "create_blank_page"),
            PendingDeprecationWarning,
            stacklevel=2,
        )
        return PageObject.create_blank_page(pdf, width, height)

    def rotate(self, angle: float) -> "PageObject":
        """
        Rotate a page clockwise by increments of 90 degrees.

        :param int angle: Angle to rotate the page.  Must be an increment
            of 90 deg.
        """
        if angle % 90 != 0:
            raise ValueError("Rotation angle must be a multiple of 90")
        rotate_obj = self.get(PG.ROTATE, 0)
        current_angle = (
            rotate_obj if isinstance(rotate_obj, int) else rotate_obj.get_object()
        )
        self[NameObject(PG.ROTATE)] = NumberObject(current_angle + angle)
        return self

    def rotate_clockwise(self, angle: float) -> "PageObject":
        warnings.warn(
            DEPR_MSG.format("rotate_clockwise", "rotate"),
            PendingDeprecationWarning,
            stacklevel=2,
        )
        return self.rotate(angle)

    def rotateClockwise(self, angle: float) -> "PageObject":
        """
        .. deprecated:: 1.28.0

            Use :meth:`rotate_clockwise` instead.
        """
        warnings.warn(
            DEPR_MSG.format("rotateClockwise", "rotate"),
            PendingDeprecationWarning,
            stacklevel=2,
        )
        return self.rotate(angle)

    def rotateCounterClockwise(self, angle: float) -> "PageObject":
        """
        .. deprecated:: 1.28.0

            Use :meth:`rotate_clockwise` with a negative argument instead.
        """
        warnings.warn(
            DEPR_MSG.format("rotateCounterClockwise", "rotate"),
            PendingDeprecationWarning,
            stacklevel=2,
        )
        return self.rotate(-angle)

    @staticmethod
    def _merge_resources(
        res1: DictionaryObject, res2: DictionaryObject, resource: Any
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        new_res = DictionaryObject()
        new_res.update(res1.get(resource, DictionaryObject()).get_object())
        page2res = cast(
            DictionaryObject, res2.get(resource, DictionaryObject()).get_object()
        )
        rename_res = {}
        for key in list(page2res.keys()):
            if key in new_res and new_res.raw_get(key) != page2res.raw_get(key):
                newname = NameObject(key + str(uuid.uuid4()))
                rename_res[key] = newname
                new_res[newname] = page2res[key]
            elif key not in new_res:
                new_res[key] = page2res.raw_get(key)
        return new_res, rename_res

    @staticmethod
    def _content_stream_rename(
        stream: ContentStream, rename: Dict[Any, Any], pdf: Any  # PdfReader
    ) -> ContentStream:
        if not rename:
            return stream
        stream = ContentStream(stream, pdf)
        for operands, _operator in stream.operations:
            if isinstance(operands, list):
                for i in range(len(operands)):
                    op = operands[i]
                    if isinstance(op, NameObject):
                        operands[i] = rename.get(op, op)
            elif isinstance(operands, dict):
                for i in operands:
                    op = operands[i]
                    if isinstance(op, NameObject):
                        operands[i] = rename.get(op, op)
            else:
                raise KeyError("type of operands is %s" % type(operands))
        return stream

    @staticmethod
    def _push_pop_gs(contents: Any, pdf: Any) -> ContentStream:  # PdfReader
        # adds a graphics state "push" and "pop" to the beginning and end
        # of a content stream.  This isolates it from changes such as
        # transformation matricies.
        stream = ContentStream(contents, pdf)
        stream.operations.insert(0, ([], "q"))
        stream.operations.append(([], "Q"))
        return stream

    @staticmethod
    def _add_transformation_matrix(
        contents: Any, pdf: Any, ctm: CompressedTransformationMatrix
    ) -> ContentStream:  # PdfReader
        # adds transformation matrix at the beginning of the given
        # contents stream.
        a, b, c, d, e, f = ctm
        contents = ContentStream(contents, pdf)
        contents.operations.insert(
            0,
            [
                [
                    FloatObject(a),
                    FloatObject(b),
                    FloatObject(c),
                    FloatObject(d),
                    FloatObject(e),
                    FloatObject(f),
                ],
                " cm",
            ],
        )
        return contents

    def get_contents(self) -> Optional[ContentStream]:
        """
        Access the page contents.

        :return: the ``/Contents`` object, or ``None`` if it doesn't exist.
            ``/Contents`` is optional, as described in PDF Reference  7.7.3.3
        """
        if PG.CONTENTS in self:
            return self[PG.CONTENTS].get_object()  # type: ignore
        else:
            return None

    def getContents(self) -> Optional[ContentStream]:
        """
        .. deprecated:: 1.28.0

            Use :meth:`get_contents` instead.
        """
        warnings.warn(
            DEPR_MSG.format("getContents", "get_contents"),
        )
        return self.get_contents()

    def merge_page(self, page2: "PageObject", expand: bool = False) -> None:
        """
        Merge the content streams of two pages into one.

        Resource references
        (i.e. fonts) are maintained from both pages.  The mediabox/cropbox/etc
        of this page are not altered.  The parameter page's content stream will
        be added to the end of this page's content stream, meaning that it will
        be drawn after, or "on top" of this page.

        :param PageObject page2: The page to be merged into this one. Should be
            an instance of :class:`PageObject<PageObject>`.
        :param bool expand: If true, the current page dimensions will be
            expanded to accommodate the dimensions of the page to be merged.
        """
        self._merge_page(page2, expand=expand)

    def mergePage(self, page2: "PageObject") -> None:
        """
        .. deprecated:: 1.28.0

            Use :meth:`merge_page` instead.
        """
        warnings.warn(
            DEPR_MSG.format("mergePage", "merge_page"),
        )
        return self.merge_page(page2)

    def _merge_page(
        self,
        page2: "PageObject",
        page2transformation: Optional[Callable[[Any], ContentStream]] = None,
        ctm: Optional[CompressedTransformationMatrix] = None,
        expand: bool = False,
    ) -> None:
        # First we work on merging the resource dictionaries.  This allows us
        # to find out what symbols in the content streams we might need to
        # rename.

        new_resources = DictionaryObject()
        rename = {}
        original_resources = cast(DictionaryObject, self[PG.RESOURCES].get_object())
        page2resources = cast(DictionaryObject, page2[PG.RESOURCES].get_object())
        new_annots = ArrayObject()

        for page in (self, page2):
            if PG.ANNOTS in page:
                annots = page[PG.ANNOTS]
                if isinstance(annots, ArrayObject):
                    for ref in annots:
                        new_annots.append(ref)

        for res in (
            RES.EXT_G_STATE,
            RES.FONT,
            RES.XOBJECT,
            RES.COLOR_SPACE,
            RES.PATTERN,
            RES.SHADING,
            RES.PROPERTIES,
        ):
            new, newrename = PageObject._merge_resources(
                original_resources, page2resources, res
            )
            if new:
                new_resources[NameObject(res)] = new
                rename.update(newrename)

        # Combine /ProcSet sets.
        new_resources[NameObject(RES.PROC_SET)] = ArrayObject(
            frozenset(
                original_resources.get(RES.PROC_SET, ArrayObject()).get_object()  # type: ignore
            ).union(
                frozenset(page2resources.get(RES.PROC_SET, ArrayObject()).get_object())  # type: ignore
            )
        )

        new_content_array = ArrayObject()

        original_content = self.get_contents()
        if original_content is not None:
            new_content_array.append(
                PageObject._push_pop_gs(original_content, self.pdf)
            )

        page2content = page2.get_contents()
        if page2content is not None:
            page2content = ContentStream(page2content, self.pdf)
            page2content.operations.insert(
                0,
                (
                    map(
                        FloatObject,
                        [
                            page2.trimbox.left,
                            page2.trimbox.bottom,
                            page2.trimbox.width,
                            page2.trimbox.height,
                        ],
                    ),
                    "re",
                ),
            )
            page2content.operations.insert(1, ([], "W"))
            page2content.operations.insert(2, ([], "n"))
            if page2transformation is not None:
                page2content = page2transformation(page2content)
            page2content = PageObject._content_stream_rename(
                page2content, rename, self.pdf
            )
            page2content = PageObject._push_pop_gs(page2content, self.pdf)
            new_content_array.append(page2content)

        # if expanding the page to fit a new page, calculate the new media box size
        if expand:
            corners1 = [
                self.mediabox.left.as_numeric(),
                self.mediabox.bottom.as_numeric(),
                self.mediabox.right.as_numeric(),
                self.mediabox.top.as_numeric(),
            ]
            corners2 = [
                page2.mediabox.left.as_numeric(),
                page2.mediabox.bottom.as_numeric(),
                page2.mediabox.left.as_numeric(),
                page2.mediabox.top.as_numeric(),
                page2.mediabox.right.as_numeric(),
                page2.mediabox.top.as_numeric(),
                page2.mediabox.right.as_numeric(),
                page2.mediabox.bottom.as_numeric(),
            ]
            if ctm is not None:
                ctm = tuple(float(x) for x in ctm)  # type: ignore[assignment]
                new_x = [
                    ctm[0] * corners2[i] + ctm[2] * corners2[i + 1] + ctm[4]
                    for i in range(0, 8, 2)
                ]
                new_y = [
                    ctm[1] * corners2[i] + ctm[3] * corners2[i + 1] + ctm[5]
                    for i in range(0, 8, 2)
                ]
            else:
                new_x = corners2[0:8:2]
                new_y = corners2[1:8:2]
            lowerleft = (min(new_x), min(new_y))
            upperright = (max(new_x), max(new_y))
            lowerleft = (min(corners1[0], lowerleft[0]), min(corners1[1], lowerleft[1]))
            upperright = (
                max(corners1[2], upperright[0]),
                max(corners1[3], upperright[1]),
            )

            self.mediabox.lower_left = lowerleft
            self.mediabox.upper_right = upperright

        self[NameObject(PG.CONTENTS)] = ContentStream(new_content_array, self.pdf)
        self[NameObject(PG.RESOURCES)] = new_resources
        self[NameObject(PG.ANNOTS)] = new_annots

    def mergeTransformedPage(
        self,
        page2: "PageObject",
        ctm: Union[CompressedTransformationMatrix, Transformation],
        expand: bool = False,
    ) -> None:
        """
        mergeTransformedPage is similar to merge_page, but a transformation
        matrix is applied to the merged stream.

        :param PageObject page2: The page to be merged into this one. Should be
            an instance of :class:`PageObject<PageObject>`.
        :param tuple ctm: a 6-element tuple containing the operands of the
            transformation matrix
        :param bool expand: Whether the page should be expanded to fit the dimensions
            of the page to be merged.

        .. deprecated:: 1.28.0

            Use :meth:`add_transformation`  and :meth:`merge_page` instead.
        """
        warnings.warn(
            DEPR_MSG.format(
                "page.mergeTransformedPage(page2, ctm)",
                "page2.add_transformation(ctm); page.merge_page(page2)",
            ),
            PendingDeprecationWarning,
            stacklevel=2,
        )
        if isinstance(ctm, Transformation):
            ctm = ctm.ctm
        ctm = cast(CompressedTransformationMatrix, ctm)
        self._merge_page(
            page2,
            lambda page2Content: PageObject._add_transformation_matrix(
                page2Content, page2.pdf, ctm  # type: ignore[arg-type]
            ),
            ctm,
            expand,
        )

    def mergeScaledPage(
        self, page2: "PageObject", scale: float, expand: bool = False
    ) -> None:
        """
        mergeScaledPage is similar to merge_page, but the stream to be merged
        is scaled by appling a transformation matrix.

        :param PageObject page2: The page to be merged into this one. Should be
            an instance of :class:`PageObject<PageObject>`.
        :param float scale: The scaling factor
        :param bool expand: Whether the page should be expanded to fit the
            dimensions of the page to be merged.

        .. deprecated:: 1.28.0

            Use :meth:`add_transformation` and :meth:`merge_page` instead.
        """
        warnings.warn(
            "page.mergeScaledPage(page2, scale, expand) method will be deprecated. "
            "Use "
            "page2.add_transformation(Transformation().scale(scale)); "
            "page.merge_page(page2, expand) instead.",
            PendingDeprecationWarning,
            stacklevel=2,
        )
        op = Transformation().scale(scale, scale)
        self.mergeTransformedPage(page2, op, expand)

    def mergeRotatedPage(
        self, page2: "PageObject", rotation: float, expand: bool = False
    ) -> None:
        """
        mergeRotatedPage is similar to merge_page, but the stream to be merged
        is rotated by appling a transformation matrix.

        :param PageObject page2: the page to be merged into this one. Should be
            an instance of :class:`PageObject<PageObject>`.
        :param float rotation: The angle of the rotation, in degrees
        :param bool expand: Whether the page should be expanded to fit the
            dimensions of the page to be merged.

        .. deprecated:: 1.28.0

            Use :meth:`add_transformation` and :meth:`merge_page` instead.
        """
        warnings.warn(
            "page.mergeRotatedPage(page2, rotation, expand) method will be deprecated. "
            "Use "
            "page2.add_transformation(Transformation().rotate(rotation)); "
            "page.merge_page(page2, expand) instead.",
            PendingDeprecationWarning,
            stacklevel=2,
        )
        op = Transformation().rotate(rotation)
        self.mergeTransformedPage(page2, op, expand)

    def mergeTranslatedPage(
        self, page2: "PageObject", tx: float, ty: float, expand: bool = False
    ) -> None:
        """
        mergeTranslatedPage is similar to merge_page, but the stream to be
        merged is translated by appling a transformation matrix.

        :param PageObject page2: the page to be merged into this one. Should be
            an instance of :class:`PageObject<PageObject>`.
        :param float tx: The translation on X axis
        :param float ty: The translation on Y axis
        :param bool expand: Whether the page should be expanded to fit the
            dimensions of the page to be merged.

        .. deprecated:: 1.28.0

            Use :meth:`add_transformation` and :meth:`merge_page` instead.
        """
        warnings.warn(
            "page.mergeTranslatedPage(page2, tx, ty, expand) method will be deprecated. "
            "Use "
            "page2.add_transformation(Transformation().translate(tx, ty)); "
            "page.merge_page(page2, expand) instead.",
            PendingDeprecationWarning,
            stacklevel=2,
        )
        op = Transformation().translate(tx, ty)
        self.mergeTransformedPage(page2, op, expand)

    def mergeRotatedTranslatedPage(
        self,
        page2: "PageObject",
        rotation: float,
        tx: float,
        ty: float,
        expand: bool = False,
    ) -> None:
        """
        mergeRotatedTranslatedPage is similar to merge_page, but the stream to
        be merged is rotated and translated by appling a transformation matrix.

        :param PageObject page2: the page to be merged into this one. Should be
            an instance of :class:`PageObject<PageObject>`.
        :param float tx: The translation on X axis
        :param float ty: The translation on Y axis
        :param float rotation: The angle of the rotation, in degrees
        :param bool expand: Whether the page should be expanded to fit the
            dimensions of the page to be merged.

        .. deprecated:: 1.28.0

            Use :meth:`add_transformation` and :meth:`merge_page` instead.
        """
        warnings.warn(
            "page.mergeRotatedTranslatedPage(page2, rotation, tx, ty, expand) "
            "method will be deprecated. Use "
            "page2.add_transformation(Transformation().rotate(rotation).translate(tx, ty)); "
            "page.merge_page(page2, expand) instead.",
            PendingDeprecationWarning,
            stacklevel=2,
        )
        op = Transformation().translate(-tx, -ty).rotate(rotation).translate(tx, ty)
        return self.mergeTransformedPage(page2, op, expand)

    def mergeRotatedScaledPage(
        self, page2: "PageObject", rotation: float, scale: float, expand: bool = False
    ) -> None:
        """
        mergeRotatedScaledPage is similar to merge_page, but the stream to be
        merged is rotated and scaled by appling a transformation matrix.

        :param PageObject page2: the page to be merged into this one. Should be
            an instance of :class:`PageObject<PageObject>`.
        :param float rotation: The angle of the rotation, in degrees
        :param float scale: The scaling factor
        :param bool expand: Whether the page should be expanded to fit the
            dimensions of the page to be merged.

        .. deprecated:: 1.28.0

            Use :meth:`add_transformation` and :meth:`merge_page` instead.
        """
        warnings.warn(
            "page.mergeRotatedScaledPage(page2, rotation, scale, expand) "
            "method will be deprecated. Use "
            "page2.add_transformation(Transformation().rotate(rotation).scale(scale)); "
            "page.merge_page(page2, expand) instead.",
            PendingDeprecationWarning,
            stacklevel=2,
        )
        op = Transformation().rotate(rotation).scale(scale, scale)
        self.mergeTransformedPage(page2, op, expand)

    def mergeScaledTranslatedPage(
        self,
        page2: "PageObject",
        scale: float,
        tx: float,
        ty: float,
        expand: bool = False,
    ) -> None:
        """
        mergeScaledTranslatedPage is similar to merge_page, but the stream to be
        merged is translated and scaled by appling a transformation matrix.

        :param PageObject page2: the page to be merged into this one. Should be
            an instance of :class:`PageObject<PageObject>`.
        :param float scale: The scaling factor
        :param float tx: The translation on X axis
        :param float ty: The translation on Y axis
        :param bool expand: Whether the page should be expanded to fit the
            dimensions of the page to be merged.

        .. deprecated:: 1.28.0

            Use :meth:`add_transformation` and :meth:`merge_page` instead.
        """
        warnings.warn(
            "page.mergeScaledTranslatedPage(page2, scale, tx, ty, expand) "
            "method will be deprecated. Use "
            "page2.add_transformation(Transformation().scale(scale).translate(tx, ty)); "
            "page.merge_page(page2, expand) instead.",
            PendingDeprecationWarning,
            stacklevel=2,
        )
        op = Transformation().scale(scale, scale).translate(tx, ty)
        return self.mergeTransformedPage(page2, op, expand)

    def mergeRotatedScaledTranslatedPage(
        self,
        page2: "PageObject",
        rotation: float,
        scale: float,
        tx: float,
        ty: float,
        expand: bool = False,
    ) -> None:
        """
        mergeRotatedScaledTranslatedPage is similar to merge_page, but the
        stream to be merged is translated, rotated and scaled by appling a
        transformation matrix.

        :param PageObject page2: the page to be merged into this one. Should be
            an instance of :class:`PageObject<PageObject>`.
        :param float tx: The translation on X axis
        :param float ty: The translation on Y axis
        :param float rotation: The angle of the rotation, in degrees
        :param float scale: The scaling factor
        :param bool expand: Whether the page should be expanded to fit the
            dimensions of the page to be merged.

        .. deprecated:: 1.28.0

            Use :meth:`add_transformation` and :meth:`merge_page` instead.
        """
        warnings.warn(
            "page.mergeRotatedScaledTranslatedPage(page2, rotation, tx, ty, expand) "
            "method will be deprecated. Use "
            "page2.add_transformation(Transformation().rotate(rotation).scale(scale)); "
            "page.merge_page(page2, expand) instead.",
            PendingDeprecationWarning,
            stacklevel=2,
        )
        op = Transformation().rotate(rotation).scale(scale, scale).translate(tx, ty)
        self.mergeTransformedPage(page2, op, expand)

    def add_transformation(
        self,
        ctm: Union[Transformation, CompressedTransformationMatrix],
        expand: bool = False,
    ) -> None:
        """
        Apply a transformation matrix to the page.

        :param tuple ctm: A 6-element tuple containing the operands of the
            transformation matrix. Alternatively, a
            :py:class:`Transformation<PyPDF2.Transformation>`
            object can be passed.

        See :doc:`/user/cropping-and-transforming`.
        """
        if isinstance(ctm, Transformation):
            ctm = ctm.ctm
        content = self.get_contents()
        if content is not None:
            content = PageObject._add_transformation_matrix(content, self.pdf, ctm)
            content = PageObject._push_pop_gs(content, self.pdf)
            self[NameObject(PG.CONTENTS)] = content
        # if expanding the page to fit a new page, calculate the new media box size
        if expand:
            corners = [
                self.mediabox.left.as_numeric(),
                self.mediabox.bottom.as_numeric(),
                self.mediabox.left.as_numeric(),
                self.mediabox.top.as_numeric(),
                self.mediabox.right.as_numeric(),
                self.mediabox.top.as_numeric(),
                self.mediabox.right.as_numeric(),
                self.mediabox.bottom.as_numeric(),
            ]

            ctm = tuple(float(x) for x in ctm)  # type: ignore[assignment]
            new_x = [
                ctm[0] * corners[i] + ctm[2] * corners[i + 1] + ctm[4]
                for i in range(0, 8, 2)
            ]
            new_y = [
                ctm[1] * corners[i] + ctm[3] * corners[i + 1] + ctm[5]
                for i in range(0, 8, 2)
            ]

            lowerleft = (min(new_x), min(new_y))
            upperright = (max(new_x), max(new_y))
            lowerleft = (min(corners[0], lowerleft[0]), min(corners[1], lowerleft[1]))
            upperright = (
                max(corners[2], upperright[0]),
                max(corners[3], upperright[1]),
            )

            self.mediabox.lower_left = lowerleft
            self.mediabox.upper_right = upperright

    def addTransformation(self, ctm: CompressedTransformationMatrix) -> None:
        """
        .. deprecated:: 1.28.0

            Use :meth:`add_transformation` instead.
        """
        warnings.warn(
            DEPR_MSG.format("addTransformation", "add_transformation"),
            PendingDeprecationWarning,
            stacklevel=2,
        )
        self.add_transformation(ctm)

    def scale(self, sx: float, sy: float) -> None:
        """
        Scale a page by the given factors by appling a transformation
        matrix to its content and updating the page size.

        :param float sx: The scaling factor on horizontal axis.
        :param float sy: The scaling factor on vertical axis.
        """
        self.add_transformation((sx, 0, 0, sy, 0, 0))
        self.mediabox = RectangleObject(
            (
                float(self.mediabox.left) * sx,
                float(self.mediabox.bottom) * sy,
                float(self.mediabox.right) * sx,
                float(self.mediabox.top) * sy,
            )
        )
        if PG.VP in self:
            viewport = self[PG.VP]
            if isinstance(viewport, ArrayObject):
                bbox = viewport[0]["/BBox"]
            else:
                bbox = viewport["/BBox"]  # type: ignore
            scaled_bbox = RectangleObject(
                (
                    float(bbox[0]) * sx,
                    float(bbox[1]) * sy,
                    float(bbox[2]) * sx,
                    float(bbox[3]) * sy,
                )
            )
            if isinstance(viewport, ArrayObject):
                self[NameObject(PG.VP)][NumberObject(0)][  # type: ignore
                    NameObject("/BBox")
                ] = scaled_bbox
            else:
                self[NameObject(PG.VP)][NameObject("/BBox")] = scaled_bbox  # type: ignore

    def scale_by(self, factor: float) -> None:
        """
        Scale a page by the given factor by appling a transformation
        matrix to its content and updating the page size.

        :param float factor: The scaling factor (for both X and Y axis).
        """
        self.scale(factor, factor)

    def scaleBy(self, factor: float) -> None:
        """
        .. deprecated:: 1.28.0

            Use :meth:`scale_by` instead.
        """
        warnings.warn(
            DEPR_MSG.format("Page.scaleBy", "Page.scale_by"),
            PendingDeprecationWarning,
            stacklevel=2,
        )
        self.scale(factor, factor)

    def scale_to(self, width: float, height: float) -> None:
        """
        Scale a page to the specified dimentions by appling a
        transformation matrix to its content and updating the page size.

        :param float width: The new width.
        :param float height: The new heigth.
        """
        sx = width / float(self.mediabox.width)
        sy = height / float(self.mediabox.height)
        self.scale(sx, sy)

    def scaleTo(self, width: float, height: float) -> None:
        """
        .. deprecated:: 1.28.0

            Use :meth:`scale_to` instead.
        """
        warnings.warn(
            DEPR_MSG.format("Page.scaleTo", "Page.scale_to"),
            PendingDeprecationWarning,
            stacklevel=2,
        )
        self.scale_to(width, height)

    def compress_content_streams(self) -> None:
        """
        Compress the size of this page by joining all content streams and
        applying a FlateDecode filter.

        However, it is possible that this function will perform no action if
        content stream compression becomes "automatic" for some reason.
        """
        content = self.get_contents()
        if content is not None:
            if not isinstance(content, ContentStream):
                content = ContentStream(content, self.pdf)
            self[NameObject(PG.CONTENTS)] = content.flate_encode()

    def compressContentStreams(self) -> None:
        """
        .. deprecated:: 1.28.0

            Use :meth:`compress_content_streams` instead.
        """
        warnings.warn(
            DEPR_MSG.format(
                "Page.compressContentStreams", "Page.compress_content_streams"
            ),
            PendingDeprecationWarning,
            stacklevel=2,
        )
        self.compress_content_streams()

    def extract_text(self, Tj_sep: str = "", TJ_sep: str = "") -> str:
        """
        Locate all text drawing commands, in the order they are provided in the
        content stream, and extract the text.  This works well for some PDF
        files, but poorly for others, depending on the generator used.  This will
        be refined in the future.  Do not rely on the order of text coming out of
        this function, as it will change if this function is made more
        sophisticated.

        :return: a string object.
        """
        text = ""
        content = self[PG.CONTENTS].get_object()
        if not isinstance(content, ContentStream):
            content = ContentStream(content, self.pdf)
        # Note: we check all strings are TextStringObjects.  ByteStringObjects
        # are strings where the byte->string encoding was unknown, so adding
        # them to the text here would be gibberish.

        space_scale = 1.0

        for operands, operator in content.operations:
            if operator == b_("Tf"):  # text font
                pass
            elif operator == b_("Tfs"):  # text font size
                pass
            elif operator == b_("Tc"):  # character spacing
                # See '5.2.1 Character Spacing'
                pass
            elif operator == b_("Tw"):  # word spacing
                # See '5.2.2 Word Spacing'
                space_scale = 1.0 + float(operands[0])
            elif operator == b_("Th"):  # horizontal scaling
                # See '5.2.3 Horizontal Scaling'
                pass
            elif operator == b_("Tl"):  # leading
                # See '5.2.4 Leading'
                pass
            elif operator == b_("Tmode"):  # text rendering mode
                # See '5.2.5 Text Rendering Mode'
                pass
            elif operator == b_("Trise"):  # text rise
                # See '5.2.6 Text Rise'
                pass
            elif operator == b_("Tj"):
                # See 'TABLE 5.6 Text-showing operators'
                _text = operands[0]
                if isinstance(_text, TextStringObject):
                    text += Tj_sep
                    text += _text
                    text += "\n"
            elif operator == b_("T*"):
                # See 'TABLE 5.5 Text-positioning operators'
                text += "\n"
            elif operator == b_("'"):
                # See 'TABLE 5.6 Text-showing operators'
                text += "\n"
                _text = operands[0]
                if isinstance(_text, TextStringObject):
                    text += operands[0]
            elif operator == b_('"'):
                # See 'TABLE 5.6 Text-showing operators'
                _text = operands[2]
                if isinstance(_text, TextStringObject):
                    text += "\n"
                    text += _text
            elif operator == b_("TJ"):
                # See 'TABLE 5.6 Text-showing operators'
                for i in operands[0]:
                    if isinstance(i, TextStringObject):
                        text += TJ_sep
                        text += i
                    elif isinstance(i, (NumberObject, FloatObject)):
                        # a positive value decreases and the negative value increases
                        # space
                        if int(i) < -space_scale * 250:
                            if len(text) == 0 or text[-1] != " ":
                                text += " "
                        else:
                            if len(text) > 1 and text[-1] == " ":
                                text = text[:-1]
                text += "\n"
        return text

    def extractText(self, Tj_sep: str = "", TJ_sep: str = "") -> str:
        """
        .. deprecated:: 1.28.0

            Use :meth:`extract_text` instead.
        """
        warnings.warn(
            DEPR_MSG.format("Page.extractText", "Page.extract_text"),
            PendingDeprecationWarning,
            stacklevel=2,
        )
        return self.extract_text(Tj_sep=Tj_sep, TJ_sep=TJ_sep)

    mediabox = _create_rectangle_accessor(PG.MEDIABOX, ())
    """
    A :class:`RectangleObject<PyPDF2.generic.RectangleObject>`, expressed in default user space units,
    defining the boundaries of the physical medium on which the page is
    intended to be displayed or printed.
    """

    @property
    def mediaBox(self) -> RectangleObject:
        """
        .. deprecated:: 1.28.0

            Use :py:attr:`mediabox` instead.
        """
        warnings.warn(
            DEPR_MSG.format("Page.mediaBox", "Page.mediabox"),
            PendingDeprecationWarning,
            stacklevel=2,
        )
        return self.mediabox

    @mediaBox.setter
    def mediaBox(self, value: RectangleObject) -> None:
        """
        .. deprecated:: 1.28.0

            Use :py:attr:`mediabox` instead.
        """
        warnings.warn(
            DEPR_MSG.format("Page.mediaBox", "Page.mediabox"),
            PendingDeprecationWarning,
            stacklevel=2,
        )
        self.mediabox = value

    cropbox = _create_rectangle_accessor("/CropBox", (PG.MEDIABOX,))
    """
    A :class:`RectangleObject<PyPDF2.generic.RectangleObject>`, expressed in default user space units,
    defining the visible region of default user space.  When the page is
    displayed or printed, its contents are to be clipped (cropped) to this
    rectangle and then imposed on the output medium in some
    implementation-defined manner.  Default value: same as :attr:`mediabox<mediabox>`.
    """

    @property
    def cropBox(self) -> RectangleObject:
        """
        .. deprecated:: 1.28.0

            Use :py:attr:`cropbox` instead.
        """
        warnings.warn(
            DEPR_MSG.format("Page.cropBox", "Page.cropbox"),
            PendingDeprecationWarning,
            stacklevel=2,
        )
        return self.cropbox

    @cropBox.setter
    def cropBox(self, value: RectangleObject) -> None:
        warnings.warn(
            DEPR_MSG.format("Page.cropBox", "Page.cropbox"),
            PendingDeprecationWarning,
            stacklevel=2,
        )
        self.cropbox = value

    bleedbox = _create_rectangle_accessor("/BleedBox", ("/CropBox", PG.MEDIABOX))
    """
    A :class:`RectangleObject<PyPDF2.generic.RectangleObject>`, expressed in default user space units,
    defining the region to which the contents of the page should be clipped
    when output in a production enviroment.
    """

    @property
    def bleedBox(self) -> RectangleObject:
        """
        .. deprecated:: 1.28.0

            Use :py:attr:`bleedbox` instead.
        """
        warnings.warn(
            DEPR_MSG.format("Page.bleedBox", "Page.bleedbox"),
            PendingDeprecationWarning,
            stacklevel=2,
        )
        return self.bleedbox

    @bleedBox.setter
    def bleedBox(self, value: RectangleObject) -> None:
        warnings.warn(
            DEPR_MSG.format("Page.bleedBox", "Page.bleedbox"),
            PendingDeprecationWarning,
            stacklevel=2,
        )
        self.bleedbox = value

    trimbox = _create_rectangle_accessor("/TrimBox", ("/CropBox", PG.MEDIABOX))
    """
    A :class:`RectangleObject<PyPDF2.generic.RectangleObject>`, expressed in default user space units,
    defining the intended dimensions of the finished page after trimming.
    """

    @property
    def trimBox(self) -> RectangleObject:
        """
        .. deprecated:: 1.28.0

            Use :py:attr:`trimbox` instead.
        """
        warnings.warn(
            DEPR_MSG.format("Page.trimBox", "Page.trimbox"),
            PendingDeprecationWarning,
            stacklevel=2,
        )
        return self.trimbox

    @trimBox.setter
    def trimBox(self, value: RectangleObject) -> None:
        warnings.warn(
            DEPR_MSG.format("Page.trimBox", "Page.trimbox"),
            PendingDeprecationWarning,
            stacklevel=2,
        )
        self.trimbox = value

    artbox = _create_rectangle_accessor("/ArtBox", ("/CropBox", PG.MEDIABOX))
    """
    A :class:`RectangleObject<PyPDF2.generic.RectangleObject>`, expressed in default user space units,
    defining the extent of the page's meaningful content as intended by the
    page's creator.
    """

    @property
    def artBox(self) -> RectangleObject:
        """
        .. deprecated:: 1.28.0

            Use :py:attr:`artbox` instead.
        """
        warnings.warn(
            DEPR_MSG.format("Page.artBox", "Page.artbox"),
            PendingDeprecationWarning,
            stacklevel=2,
        )
        return self.artbox

    @artBox.setter
    def artBox(self, value: RectangleObject) -> None:
        warnings.warn(
            DEPR_MSG.format("Page.artBox", "Page.artbox"),
            PendingDeprecationWarning,
            stacklevel=2,
        )
        self.artbox = value


class _VirtualList:
    def __init__(
        self,
        length_function: Callable[[], int],
        get_function: Callable[[int], PageObject],
    ) -> None:
        self.length_function = length_function
        self.get_function = get_function
        self.current = -1

    def __len__(self) -> int:
        return self.length_function()

    def __getitem__(self, index: int) -> PageObject:
        if isinstance(index, slice):
            indices = range(*index.indices(len(self)))
            cls = type(self)
            return cls(indices.__len__, lambda idx: self[indices[idx]])
        if not isinstance(index, int):
            raise TypeError("sequence indices must be integers")
        len_self = len(self)
        if index < 0:
            # support negative indexes
            index = len_self + index
        if index < 0 or index >= len_self:
            raise IndexError("sequence index out of range")
        return self.get_function(index)

    def __iter__(self) -> Iterator[PageObject]:
        for i in range(len(self)):
            yield self[i]
