import io
import os
import unittest
try:
    import urllib.request as urllib2
    from urllib.request import pathname2url
except ImportError:
    import urllib2
    from urllib import pathname2url

from contextlib import contextmanager
from lxml import etree as ET
from odml.tools.version_converter import VersionConverter

try:
    unicode = unicode
except NameError:
    unicode = str

VC = VersionConverter


class TestVersionConverter(unittest.TestCase):
    def setUp(self):
        self.doc = """
                     <odML version="1">
                        <date>2008-07-07</date>
                        <section>
                            <property>
                                <value>0<unit>deg</unit><type>int</type><uncertainty/></value>
                                <value>45<unit>deg</unit><type>int</type></value>
                                <name>Orientations</name>
                            </property>
                            <type>some sec type</type>
                            <name>sec_name</name>
                        </section>
                        <section>
                            <type>some sec type</type>
                            <name>sec_name</name>
                            <property>
                                <name>prop_name</name>
                            </property>
                            <property>
                                <name>prop_name</name>
                            </property>
                        </section>
                        <author>Author</author>
                     </odML>
                   """

    @contextmanager
    def assertNotRaises(self, exc_type):
        try:
            yield None
        except exc_type:
            raise self.failureException('{} raised'.format(exc_type.__name__))

    def test_replace_same_name_entites(self):
        root = ET.fromstring(self.doc)
        sec_names = []
        sec_elems = []
        for sec in root.iter("section"):
            sec_names.append(sec.find("name").text)
            sec_elems.append(sec)
        self.assertEqual(sec_names[0], "sec_name")
        self.assertEqual(sec_names[0], sec_names[1])

        props_names = []
        for prop in sec_elems[1].iter("property"):
            props_names.append(prop.find("name").text)
        self.assertEqual(props_names[0], "prop_name")
        self.assertEqual(props_names[0], props_names[1])

        tree = ET.ElementTree(root)
        tree = VC._replace_same_name_entities(tree)
        root = tree.getroot()
        sec_names = []
        sec_elems = []
        for sec in root.iter("section"):
            sec_names.append(sec.find("name").text)
            sec_elems.append(sec)
        self.assertEqual(sec_names[0], "sec_name")
        self.assertEqual(sec_names[1], "sec_name-2")

        props_names = []
        for prop in sec_elems[1].iter("property"):
            props_names.append(prop.find("name").text)
        self.assertEqual(props_names[0], "prop_name")
        self.assertEqual(props_names[1], "prop_name-2")

    def test_convert_odml_file(self):
        with self.assertRaises(Exception) as exc:
            VC("/not_valid_path").convert()
        self.assertIn("Cannot parse provided file", str(exc.exception))

        root = ET.fromstring(self.doc)
        prop = root.find("section").find("property")
        val_elems = []
        for val in prop.iter("value"):
            val_elems.append(val)

        self.assertEqual(val_elems[0].find("unit").text, "deg")
        self.assertEqual(val_elems[0].find("type").text, "int")
        self.assertEqual(val_elems[0].find("uncertainty").text, None)
        self.assertEqual(prop.find("unit"), None)
        self.assertEqual(prop.find("type"), None)

        file = io.StringIO(unicode(self.doc))
        vc = VC(file)
        tree = vc._convert(vc._parse_xml())
        root = tree.getroot()
        prop = root.find("section").find("property")
        val_elems = []
        for val in prop.iter("value"):
            val_elems.append(val)

        self.assertEqual(len(val_elems), 1)
        self.assertEqual(val_elems[0].find("unit"), None)
        self.assertEqual(val_elems[0].find("type"), None)
        self.assertEqual(val_elems[0].find("uncertainty"), None)
        self.assertEqual(val_elems[0].text, "[0, 45]")
        self.assertEqual(prop.find("unit").text, "deg")
        self.assertEqual(len(prop.findall("unit")), 1)
        self.assertEqual(prop.find("type").text, "int")
        self.assertEqual(len(prop.findall("type")), 1)
        self.assertEqual(prop.find("uncertainty").text, None)

    def test_convert_odml_file_document(self):
        """Test proper conversion of the odml.Document entity from
        odml model version 1 to version 1.1.

        The test checks for the proper conversion of all valid
        Document tags and exclusion of non-Document tags.
        """

        dir_path = os.path.dirname(os.path.realpath(__file__))
        repo_file = os.path.join(dir_path, "resources",
                                           "local_repository_file_v1.1.xml")
        local_url = "file://%s" % repo_file

        repo_old_file = os.path.join(dir_path, "resources",
                                               "local_repository_file_v1.0.xml")
        local_old_url = "file://%s" % repo_old_file

        doc = """
                <odML version="1">
                  <!-- Valid Document tags test -->
                  <author>Document author</author>
                  <version>1</version>
                  <date>2017-10-18</date>
                  <repository>%s</repository>
                  <section><name>Document section</name></section>
                
                  <!-- Unsupported Document tags test -->
                  <invalid>Invalid Document tag</invalid>
                  <property>Invalid Document property</property>
                  <value>Invalid Document value</value>
                </odML>
        """ % local_url

        invalid_repo_doc = """
                <odML version="1">
                  <repository>Unresolvable</repository>
                  <section><name>Document section</name></section>
                </odML>
        """

        old_repo_doc = """
                <odML version="1">
                  <repository>%s</repository>
                  <section><name>Document section</name></section>
                </odML>
        """ % local_old_url

        file = io.StringIO(unicode(doc))
        vc = VC(file)
        conv_doc = vc._convert(vc._parse_xml())
        root = conv_doc.getroot()
        # Test export of Document tags, repository is excluded
        self.assertEqual(len(root.findall("author")), 1)
        self.assertEqual(len(root.findall("date")), 1)
        self.assertEqual(len(root.findall("repository")), 1)
        self.assertEqual(len(root.findall("section")), 1)

        # Test absence of non-Document tags
        self.assertEqual(len(root.findall("invalid")), 0)
        self.assertEqual(len(root.findall("property")), 0)
        self.assertEqual(len(root.findall("value")), 0)

        # Test warning message on non-importable repository
        file = io.StringIO(unicode(invalid_repo_doc))
        vc = VC(file)
        conv_doc = vc._convert(vc._parse_xml())
        root = conv_doc.getroot()
        self.assertEqual(root.findall("repository")[0].text, "Unresolvable")
        self.assertIn("not odML v1.1 compatible", vc.conversion_log[0])

        # Test warning message on old repository
        file = io.StringIO(unicode(old_repo_doc))
        vc = VC(file)
        conv_doc = vc._convert(vc._parse_xml())
        root = conv_doc.getroot()
        self.assertEqual(root.findall("repository")[0].text, local_old_url)
        self.assertIn("not odML v1.1 compatible", vc.conversion_log[0])

    def test_convert_odml_file_section(self):
        """Test proper conversion of the odml.Section entity from
        odml model version 1 to version 1.1.

        The test checks for the proper conversion of all valid
        Section tags and exclusion of non-Section tags.
        """

        dir_path = os.path.dirname(os.path.realpath(__file__))
        repo_file = os.path.join(dir_path, "resources",
                                           "local_repository_file_v1.1.xml")
        local_url = "file://%s" % repo_file

        repo_old_file = os.path.join(dir_path, "resources",
                                               "local_repository_file_v1.0.xml")
        local_old_url = "file://%s" % repo_old_file

        doc = """
                <odML version="1">
                  <!-- Valid Section tags test -->
                  <section>
                    <name>Section name</name>
                    <type>Section type</type>
                    <definition>Section definition</definition>
                    <reference>Section reference</reference>
                    <link>Section link</link>
                    <repository>%s</repository>
                    <include>Section include</include>
                    <property><name>Section Property 1</name></property>
                    <property><name>Section Property 2</name></property>
                
                    <section>
                      <name>SubSection name</name>
                      <type>SubSection type</type>
                      <definition>SubSection definition</definition>
                      <reference>SubSection reference</reference>
                      <link>SubSection link</link>
                      <repository>%s</repository>
                      <include>SubSection include</include>
                      <property><name>SubSection Property</name></property>
                    </section>
                  </section>
                
                  <section>
                    <name>Unsupported Section tags test</name>
                    <invalid>Invalid tag</invalid>
                    <value>Invalid Value tag</value>
                    <mapping>Unsupported mapping tag</mapping>
                  </section>
                </odML>
        """ % (local_url, local_url)

        file = io.StringIO(unicode(doc))
        vc = VC(file)
        conv_doc = vc._convert(vc._parse_xml())
        root = conv_doc.getroot()

        sec = root.findall("section")
        self.assertEqual(len(sec), 2)

        # Test valid section tags.
        self.assertEqual(len(sec[0]), 10)
        self.assertEqual(sec[0].find("name").text, "Section name")
        self.assertEqual(sec[0].find("type").text, "Section type")
        self.assertEqual(sec[0].find("definition").text, "Section definition")
        self.assertEqual(sec[0].find("reference").text, "Section reference")
        self.assertEqual(sec[0].find("link").text, "Section link")
        self.assertEqual(sec[0].find("repository").text, local_url)
        self.assertEqual(sec[0].find("include").text, "Section include")
        self.assertEqual(len(sec[0].findall("property")), 2)
        self.assertEqual(len(sec[0].findall("section")), 1)

        # Test valid subsection tags.
        subsec = sec[0].find("section")
        self.assertEqual(len(subsec), 8)
        self.assertEqual(subsec.find("name").text, "SubSection name")
        self.assertEqual(subsec.find("type").text, "SubSection type")
        self.assertEqual(subsec.find("definition").text, "SubSection definition")
        self.assertEqual(subsec.find("reference").text, "SubSection reference")
        self.assertEqual(subsec.find("link").text, "SubSection link")
        self.assertEqual(subsec.find("repository").text, local_url)
        self.assertEqual(subsec.find("include").text, "SubSection include")
        self.assertEqual(len(subsec.findall("property")), 1)

        # Test absence of non-Section tags
        self.assertEqual(len(sec[1]), 1)
        self.assertEqual(len(sec[1].findall("name")), 1)

        # Test presence of v1.0 repository tag and warning log entry
        doc = """
                <odML version="1">
                  <section>
                    <name>Unsupported Section include test</name>
                    <repository>%s</repository>
                  </section>
                </odML>""" % local_old_url

        file = io.StringIO(unicode(doc))
        vc = VC(file)
        conv_doc = vc._convert(vc._parse_xml())
        sec = conv_doc.getroot().findall("section")
        self.assertEqual(sec[0].find("repository").text, local_old_url)
        self.assertIn("not odML v1.1 compatible", vc.conversion_log[0])

        # Test presence of v1.0 include tag and warning log entry
        doc = """
                <odML version="1">
                  <section>
                    <name>Unsupported Section include test</name>
                    <include>%s</include>
                  </section>
                </odML>""" % local_old_url

        file = io.StringIO(unicode(doc))
        vc = VC(file)
        conv_doc = vc._convert(vc._parse_xml())
        sec = conv_doc.getroot().findall("section")

        self.assertEqual(sec[0].find("include").text, local_old_url)
        self.assertIn("not odML v1.1 compatible", vc.conversion_log[0])

    def test_convert_odml_file_property(self):
        """Test proper conversion of the odml.Property entity from
        odml model version 1 to version 1.1.

        The test checks for the proper conversion of all valid
        Property tags and exclusion of non-Property tags.
        """

        doc = """
                <odML version="1">
                  <section>
                    <name>Valid Property tags test</name>
                    <property>
                      <name>Property name</name>
                      <type>Property type</type>
                      <definition>Property definition</definition>
                      <dependency>Property dependency</dependency>
                      <dependencyvalue>Property dependency value</dependencyvalue>
                    </property>
                  </section>

                  <section>
                    <name>Unsupported Property tags test</name>
                    <property>
                      <name>Invalid Property</name>
                      <invalid>Invalid tag</invalid>
                      <section><name>Invalid Section</name></section>
                    </property>
                    <property>Property with no name</property>
                  </section>
                </odML>
        """

        file = io.StringIO(unicode(doc))
        vc = VC(file)
        conv_doc = vc._convert(vc._parse_xml())
        root = conv_doc.getroot()
        sec = root.findall("section")

        # Test valid Property tags
        self.assertEqual(sec[0].find("name").text, "Valid Property tags test")
        self.assertEqual(len(sec[0].findall("property")), 1)
        prop = sec[0].find("property")
        self.assertEqual(len(prop), 5)
        self.assertEqual(prop.find("name").text, "Property name")
        self.assertEqual(prop.find("type").text, "Property type")
        self.assertEqual(prop.find("definition").text, "Property definition")
        self.assertEqual(prop.find("dependency").text, "Property dependency")
        self.assertEqual(prop.find("dependencyvalue").text, "Property dependency value")

        # Test non-import of Property w/o name
        self.assertEqual(len(sec[1].findall("property")), 1)
        # Test absence of non-Property tags
        prop = sec[1].find("property")
        self.assertEqual(len(prop), 1)
        self.assertEqual(len(prop.findall("name")), 1)

    def test_convert_odml_file_value(self):
        """Test proper conversion of the odml.Value entity from
        odml model version 1 to version 1.1.

        The test checks for the proper conversion of all valid
        Value tags and exclusion of non-Value tags.
        """

        doc = """
                <odML version="1">
                  <section>
                    <name>Values export test</name>
                    <property>
                      <name>Single value export</name>
                      <value>1</value>
                    </property>
                
                    <property>
                      <name>Multiple values export</name>
                      <value>1</value>
                      <value>2</value>
                      <value>3</value>
                    </property>
                
                    <property>
                      <name>Empty value export</name>
                      <value></value>
                      <value></value>
                      <value></value>
                      <value></value>
                    </property>
                
                    <property>
                      <name>Supported Value tags export</name>
                      <value>0.1
                        <type>float</type>
                        <uncertainty>0.05</uncertainty>
                        <unit>mV</unit>
                        <filename>raw.txt</filename>
                        <reference>Value reference</reference>
                      </value>
                    </property>
                
                    <property>
                      <name>Supported Multiple Value tags export</name>
                      <value>0.1
                        <unit>mV</unit>
                        <filename>raw.txt</filename>
                        <reference>Value reference</reference>
                      </value>
                      <value>0.2
                        <type>float</type>
                        <uncertainty>0.05</uncertainty>
                        <unit>mV</unit>
                        <filename>raw.txt</filename>
                        <reference>Value reference</reference>
                      </value>
                      <value>3
                        <type>int</type>
                        <uncertainty>0.06</uncertainty>
                        <unit>kV</unit>
                        <filename>raw2.txt</filename>
                        <reference>Value reference 2</reference>
                      </value>
                    </property>
                
                    <property>
                      <name>Unsupported Value tags export</name>
                      <value>
                        <invalid>Invalid Value tag</invalid>
                        <encoder>Encoder</encoder>
                        <checksum>Checksum</checksum>
                      </value>
                    </property>
                
                  </section>
                </odML>
        """

        file = io.StringIO(unicode(doc))
        vc = VC(file)
        conv_doc = vc._convert(vc._parse_xml())
        root = conv_doc.getroot()
        sec = root.find("section")
        self.assertEqual(len(sec), 7)

        # Test single value export
        prop = sec.findall("property")[0]
        self.assertEqual(len(prop), 2)
        self.assertEqual(prop.find("value").text, "1")

        # Test multiple value export
        prop = sec.findall("property")[1]
        self.assertEqual(len(prop), 2)
        self.assertEqual(prop.find("value").text, "[1, 2, 3]")

        # Test empty value export
        prop = sec.findall("property")[2]
        self.assertEqual(len(prop), 1)
        self.assertEqual(prop.find("name").text, "Empty value export")

        # Test valid Value tags
        prop = sec.findall("property")[3]
        self.assertEqual(len(prop), 7)
        self.assertEqual(prop.find("value").text, "0.1")
        self.assertEqual(prop.find("type").text, "float")
        self.assertEqual(prop.find("uncertainty").text, "0.05")
        self.assertEqual(prop.find("unit").text, "mV")
        self.assertEqual(prop.find("value_origin").text, "raw.txt")
        self.assertEqual(prop.find("reference").text, "Value reference")
        self.assertEqual(len(prop.findall("filename")), 0)

        # Test valid multiple Value tag export
        prop = sec.findall("property")[4]
        self.assertEqual(len(prop), 7)
        self.assertEqual(prop.find("value").text, "[0.1, 0.2, 3]")
        self.assertEqual(prop.find("type").text, "float")
        self.assertEqual(prop.find("uncertainty").text, "0.05")
        self.assertEqual(prop.find("unit").text, "mV")
        self.assertEqual(prop.find("value_origin").text, "raw.txt")
        self.assertEqual(prop.find("reference").text, "Value reference")

        # Test non-export of invalid Value tags
        prop = sec.findall("property")[5]
        self.assertEqual(len(prop), 1)
        self.assertEqual(len(prop.findall("name")), 1)
