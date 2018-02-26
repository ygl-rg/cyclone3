``cyclone.escape`` --- Escaping and string manipulation
=======================================================

.. automodule:: cyclone.escape

   Escaping functions
   ------------------

   .. autofunction:: xhtml_escape
   .. autofunction:: xhtml_unescape

   .. autofunction:: url_escape
   .. autofunction:: url_unescape

   .. autofunction:: json_encode
   .. autofunction:: json_decode

   Byte/unicode conversions
   ------------------------
   These functions are used extensively within Cyclone itself,
   but should not be directly needed by most applications.

   .. autofunction:: utf8
   .. autofunction:: to_unicode
   .. function:: native_str

      Converts a byte or unicode string into type `str`.  Equivalent to
      `utf8` on Python 2 and `to_unicode` on Python 3.

   .. autofunction:: to_basestring

   .. autofunction:: recursive_unicode

   Miscellaneous functions
   -----------------------
   .. autofunction:: linkify
   .. autofunction:: squeeze
