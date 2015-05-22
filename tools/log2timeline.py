#!/usr/bin/python
# -*- coding: utf-8 -*-
"""The log2timeline front-end."""

import argparse
import logging
import multiprocessing
import sys
import time
import textwrap

import plaso
from plaso.cli import extraction_tool
from plaso.cli import tools as cli_tools
from plaso.frontend import log2timeline
from plaso.frontend import utils as frontend_utils
from plaso.lib import definitions
from plaso.lib import errors
from plaso.lib import pfilter


class Log2TimelineTool(extraction_tool.ExtractionTool):
  """Class that implements the log2timeline CLI tool."""

  NAME = u'log2timeline'
  DESCRIPTION = textwrap.dedent(u'\n'.join([
      u'',
      u'log2timeline is the main front-end to the plaso back-end, used to',
      u'collect and correlate events extracted from a filesystem.',
      u'',
      u'More information can be gathered from here:',
      u'    http://plaso.kiddaland.net/usage/log2timeline',
      u'']))

  EPILOG = textwrap.dedent(u'\n'.join([
      u'',
      u'Example usage:',
      u'',
      u'Run the tool against an image (full kitchen sink)',
      u'    log2timeline.py /cases/mycase/plaso.dump ímynd.dd',
      u'',
      u'Instead of answering questions, indicate some of the options on the',
      u'command line (including data from particular VSS stores).',
      (u'    log2timeline.py -o 63 --vss_stores 1,2 /cases/plaso_vss.dump '
       u'image.E01'),
      u'',
      u'And that is how you build a timeline using log2timeline...',
      u'']))

  def __init__(self, input_reader=None, output_writer=None):
    """Initializes the CLI tool object.

    Args:
      input_reader: the input reader (instance of InputReader).
                    The default is None which indicates the use of the stdin
                    input reader.
      output_writer: the output writer (instance of OutputWriter).
                     The default is None which indicates the use of the stdout
                     output writer.
    """
    super(Log2TimelineTool, self).__init__(
        input_reader=input_reader, output_writer=output_writer)
    self._filter_expression = None
    self._foreman_verbose = False
    self._front_end = log2timeline.Log2TimelineFrontend()
    self._stdout_output_writer = isinstance(
        self._output_writer, cli_tools.StdoutOutputWriter)
    self._status_view_mode = u'linear'
    self._output = None

    self.list_parsers_and_plugins = False
    self.list_timezones = False

  def _DebugPrintCollection(self):
    """Prints debug information about the collection."""
    if self._front_end.SourceIsStorageMediaImage():
      if self._filter_file:
        logging.debug(u'Starting a collection on image with filter.')
      else:
        logging.debug(u'Starting a collection on image.')

    elif self._front_end.SourceIsDirectory():
      if self._filter_file:
        logging.debug(u'Starting a collection on directory with filter.')
      else:
        logging.debug(u'Starting a collection on directory.')

    elif self._front_end.SourceIsFile():
      logging.debug(u'Starting a collection on a single file.')

    else:
      logging.warning(u'Unsupported source type.')

  def _ParseOutputOptions(self, options):
    """Parses the output options.

    Args:
      options: the command line arguments (instance of argparse.Namespace).

    Raises:
      BadConfigOption: if the options are invalid.
    """
    self._output_module = getattr(options, u'output_module', None)

    self._text_prepend = getattr(options, u'text_prepend', None)

  def _ParseProcessingOptions(self, options):
    """Parses the processing options.

    Args:
      options: the command line arguments (instance of argparse.Namespace).

    Raises:
      BadConfigOption: if the options are invalid.
    """
    self._single_process_mode = getattr(options, u'single_process', False)

    self._foreman_verbose = getattr(options, u'foreman_verbose', False)

    # TODO: workers.

  def _PrintStatusUpdate(self, processing_status):
    """Prints the processing status.

    Args:
      processing_status: the processsing status (instance of ProcessingStatus).
    """
    if self._stdout_output_writer:
      # ANSI escape sequence to clear screen.
      self._output_writer.Write(b'\033[2J')
      # ANSI escape sequence to move cursor to top left.
      self._output_writer.Write(b'\033[H')

    self._output_writer.Write(
        u'plaso - {0:s} version {1:s}\n'.format(
            self.NAME, plaso.GetVersion()))
    self._output_writer.Write(u'\n')

    self.PrintOptions()

    status_table = [u'\033[1mIdentifier\tPID\tStatus\t\tEvents\t\tFile\033[0m']
    for extraction_worker_status in processing_status.extraction_workers:
      status = extraction_worker_status.status
      if status == definitions.PROCESSING_STATUS_RUNNING:
        status = extraction_worker_status.process_status

      if len(status) < 8:
        status = u'{0:s}\t'.format(status)

      events = u'{0:d} ({1:d})'.format(
          extraction_worker_status.number_of_events,
          extraction_worker_status.number_of_events_delta)

      if len(events) < 8:
        events = u'{0:s}\t'.format(events)

      # TODO: shorten display name to fit in 80 chars and show the filename.
      status_row = u'{0:s}\t{1:d}\t{2:s}\t{3:s}\t{4:s}'.format(
          extraction_worker_status.identifier,
          extraction_worker_status.pid, status, events,
          extraction_worker_status.display_name)

      status_table.append(status_row)

    status_table.append(u'')
    self._output_writer.Write(u'\n'.join(status_table))
    self._output_writer.Write(u'\n')

    if processing_status.GetExtractionCompleted():
      self._output_writer.Write(
          u'All extraction workers completed - waiting for storage.\n')
      self._output_writer.Write(u'\n')

    if self._stdout_output_writer:
      # We need to explicitly flush stdout to prevent partial status updates.
      sys.stdout.flush()

  def _PrintStatusUpdateStream(self, processing_status):
    """Prints the processing status as a stream of output.

    Args:
      processing_status: the processsing status (instance of ProcessingStatus).
    """
    if processing_status.GetExtractionCompleted():
      logging.info(u'All extraction workers completed - waiting for storage.')

    else:
      for extraction_worker_status in processing_status.extraction_workers:
        status = extraction_worker_status.status
        logging.info((
            u'{0:s} (PID: {1:d}) - events extracted: {2:d} - file: {3:s} '
            u'- running: {4!s} <{5:s}>').format(
                extraction_worker_status.identifier,
                extraction_worker_status.pid,
                extraction_worker_status.number_of_events,
                extraction_worker_status.display_name,
                status == definitions.PROCESSING_STATUS_RUNNING,
                extraction_worker_status.process_status))

  def AddOutputOptions(self, argument_group):
    """Adds the output options to the argument group.

    Args:
      argument_group: The argparse argument group (instance of
                      argparse._ArgumentGroup).
    """
    argument_group.add_argument(
        u'--output', dest=u'output_module', action=u'store', type=unicode,
        default=u'', help=(
            u'Bypass the storage module directly storing events according to '
            u'the output module. This means that the output will not be in the '
            u'pstorage format but in the format chosen by the output module. '
            u'[Please note this feature is EXPERIMENTAL at this time, use at '
            u'own risk (eg. sqlite output does not yet work)]'))

    argument_group.add_argument(
        u'-t', u'--text', dest=u'text_prepend', action=u'store', type=unicode,
        default=u'', metavar=u'TEXT', help=(
            u'Define a free form text string that is prepended to each path '
            u'to make it easier to distinguish one record from another in a '
            u'timeline (like c:\\, or host_w_c:\\)'))

  def AddProcessingOptions(self, argument_group):
    """Adds the processing options to the argument group.

    Args:
      argument_group: The argparse argument group (instance of
                      argparse._ArgumentGroup).
    """
    argument_group.add_argument(
        u'--single_process', u'--single-process', dest=u'single_process',
        action=u'store_true', default=False, help=(
            u'Indicate that the tool should run in a single process.'))

    argument_group.add_argument(
        u'--show_memory_usage', u'--show-memory-usage', action=u'store_true',
        default=False, dest=u'foreman_verbose', help=(
            u'Indicates that basic memory usage should be included in the '
            u'output of the process monitor. If this option is not set the '
            u'tool only displays basic status and counter information.'))

    argument_group.add_argument(
        u'--workers', dest=u'workers', action=u'store', type=int, default=0,
        help=(u'The number of worker threads [defaults to available system '
              u'CPUs minus three].'))

  def ListPluginInformation(self):
    """Lists all plugin and parser information."""
    plugin_list = self._front_end.GetPluginData()
    lines_of_text = [
        u'{:=^80}'.format(u' log2timeline/plaso information. ')]

    for header, data in plugin_list.items():
      # TODO: Using the frontend utils here instead of "self.PrintHeader"
      # since the desired output here is a string that can be sent later
      # to an output writer. Change this entire function so it can utilize
      # PrintHeader or something similar.

      # TODO: refactor usage of frontend utils away.
      lines_of_text.append(frontend_utils.FormatHeader(header))
      for entry_header, entry_data in sorted(data):
        lines_of_text.append(
            frontend_utils.FormatOutputString(entry_header, entry_data))

    lines_of_text.append(u'')
    self._output_writer.Write(u'\n'.join(lines_of_text))

  def ParseArguments(self):
    """Parses the command line arguments.

    Returns:
      A boolean value indicating the arguments were successfully parsed.
    """
    logging.basicConfig(
        level=logging.INFO, format=u'[%(levelname)s] %(message)s')

    argument_parser = argparse.ArgumentParser(
        description=self.DESCRIPTION, epilog=self.EPILOG, add_help=False,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    self.AddBasicOptions(argument_parser)

    extraction_group = argument_parser.add_argument_group(
        u'Extraction Arguments')

    self.AddExtractionOptions(extraction_group)
    self.AddFilterOptions(extraction_group)
    self.AddStorageMediaImageOptions(extraction_group)
    self.AddTimezoneOption(extraction_group)
    self.AddVssProcessingOptions(extraction_group)

    info_group = argument_parser.add_argument_group(u'Informational Arguments')

    self.AddInformationalOptions(info_group)

    info_group.add_argument(
        u'--info', dest=u'show_info', action=u'store_true', default=False,
        help=u'Print out information about supported plugins and parsers.')

    info_group.add_argument(
        u'--logfile', u'--log_file', u'--log-file', action=u'store',
        metavar=u'FILENAME', dest=u'log_file', type=unicode, default=u'', help=(
            u'If defined all log messages will be redirected to this file '
            u'instead the default STDERR.'))

    info_group.add_argument(
        u'--status_view', u'--status-view', dest=u'status_view_mode',
        choices=[u'linear', u'window'], action=u'store',
        metavar=u'TYPE', default=u'linear', help=(
            u'The processing status view mode: "linear" or "window". '
            u'Note that the "window" mode is still experimental.'))

    output_group = argument_parser.add_argument_group(u'Output Arguments')

    self.AddOutputOptions(output_group)
    self.AddStorageOptions(output_group)

    processing_group = argument_parser.add_argument_group(
        u'Processing Arguments')

    self.AddPerformanceOptions(processing_group)
    self.AddProfilingOptions(processing_group)
    self.AddProcessingOptions(processing_group)

    argument_parser.add_argument(
        u'output', action=u'store', metavar=u'STORAGE_FILE', nargs=u'?',
        type=unicode, help=(
            u'The path to the output file, if the file exists it will get '
            u'appended to.'))

    argument_parser.add_argument(
        u'source', action=u'store', metavar=u'SOURCE', nargs=u'?', type=unicode,
        help=(
            u'The path to the source device, file or directory. If the source '
            u'is a supported storage media device or image file, archive file '
            u'or a directory, the files within are processed recursively.'))

    argument_parser.add_argument(
        u'filter', action=u'store', metavar=u'FILTER', nargs=u'?', default=None,
        type=unicode, help=(
            u'A filter that can be used to filter the dataset before it '
            u'is written into storage. More information about the filters '
            u'and its usage can be found here: http://plaso.kiddaland.'
            u'net/usage/filters'))

    try:
      options = argument_parser.parse_args()
    except UnicodeEncodeError:
      # If we get here we are attempting to print help in a non-Unicode
      # terminal.
      self._output_writer.Write(u'\n')
      self._output_writer.Write(argument_parser.format_help())
      return False

    # Properly prepare the attributes according to local encoding.
    if self.preferred_encoding == u'ascii':
      logging.warning(
          u'The preferred encoding of your system is ASCII, which is not '
          u'optimal for the typically non-ASCII characters that need to be '
          u'parsed and processed. The tool will most likely crash and die, '
          u'perhaps in a way that may not be recoverable. A five second delay '
          u'is introduced to give you time to cancel the runtime and '
          u'reconfigure your preferred encoding, otherwise continue at own '
          u'risk.')
      time.sleep(5)

    try:
      self.ParseOptions(options)
    except errors.BadConfigOption as exception:
      logging.error(u'{0:s}'.format(exception))

      self._output_writer.Write(u'\n')
      self._output_writer.Write(argument_parser.format_help())

      return False

    return True

  def ParseOptions(self, options):
    """Parses the options.

    Args:
      options: the command line arguments (instance of argparse.Namespace).

    Raises:
      BadConfigOption: if the options are invalid.
    """
    # Check the list options first otherwise required options will raise.
    self._ParseTimezoneOption(options)

    self.list_parsers_and_plugins = getattr(options, u'show_info', False)

    if self.list_timezones or self.list_parsers_and_plugins:
      return

    super(Log2TimelineTool, self).ParseOptions(options)
    self._ParseOutputOptions(options)
    self._ParseProcessingOptions(options)

    format_string = (
        u'%(asctime)s [%(levelname)s] (%(processName)-10s) PID:%(process)d '
        u'<%(module)s> %(message)s')

    log_file = getattr(options, u'log_file', None)
    if self._debug_mode:
      logging_level = logging.DEBUG
    else:
      logging_level = logging.INFO

    if log_file:
      logging.basicConfig(
          level=logging_level, format=format_string, filename=log_file)
    else:
      logging.basicConfig(level=logging_level, format=format_string)

    if self._debug_mode:
      logging_filter = log2timeline.LoggingFilter()
      root_logger = logging.getLogger()
      root_logger.addFilter(logging_filter)

    self._output = getattr(options, u'output', None)
    if not self._output:
      raise errors.BadConfigOption(u'No output defined.')

    # TODO: where is this defined?
    self._operating_system = getattr(options, u'os', None)

    if self._operating_system:
      self._mount_path = getattr(options, u'filename', None)

    self._filter_expression = getattr(options, u'filter', None)
    if self._filter_expression:
      # TODO: refactor self._filter_object out the tool into the frontend.
      self._filter_object = pfilter.GetMatcher(self._filter_expression)
      if not self._filter_object:
        raise errors.BadConfigOption(
            u'Invalid filter expression: {0:s}'.format(self._filter_expression))

    self._status_view_mode = getattr(options, u'status_view_mode', u'linear')

  def PrintOptions(self):
    """Prints the options."""
    self._output_writer.Write(
        u'Source path\t\t\t\t: {0:s}\n'.format(self._source_path))

    is_image = self._front_end.SourceIsStorageMediaImage()
    self._output_writer.Write(
        u'Is storage media image or device\t: {0!s}\n'.format(is_image))

    if is_image:
      image_offset_bytes = self._front_end.partition_offset
      if isinstance(image_offset_bytes, basestring):
        try:
          image_offset_bytes = int(image_offset_bytes, 10)
        except ValueError:
          image_offset_bytes = 0
      elif image_offset_bytes is None:
        image_offset_bytes = 0

      self._output_writer.Write(
          u'Partition offset\t\t\t: {0:d} (0x{0:08x})\n'.format(
              image_offset_bytes))

      if self._front_end.process_vss and self._front_end.vss_stores:
        self._output_writer.Write(
            u'VSS stores\t\t\t\t: {0!s}\n'.format(self._front_end.vss_stores))

    if self._filter_file:
      self._output_writer.Write(u'Filter file\t\t\t\t: {0:s}\n'.format(
          self._filter_file))

    self._output_writer.Write(u'\n')

  def ProcessSource(self):
    """Processes the source.

    Args:
      options: the command line arguments (instance of argparse.Namespace).

    Raises:
      SourceScannerError: if the source scanner could not find a supported
                          file system.
      UserAbort: if the user initiated an abort.
    """
    self._front_end.SetEnableProfiling(
        self._enable_profiling,
        profiling_sample_rate=self._profiling_sample_rate,
        profiling_type=self._profiling_type)
    self._front_end.SetStorageFile(self._output)
    self._front_end.SetShowMemoryInformation(show_memory=self._foreman_verbose)

    self._front_end.ScanSource(
        self._source_path, partition_number=self._partition_number,
        partition_offset=self._partition_offset, enable_vss=self._process_vss,
        vss_stores=self._vss_stores)

    self._output_writer.Write(u'\n')
    self.PrintOptions()

    # TODO: merge this into the output of PrintOptions.
    self._DebugPrintCollection()

    logging.info(u'Processing started.')

    if self._status_view_mode == u'linear':
      status_update_callback = self._PrintStatusUpdateStream
    elif self._status_view_mode == u'window':
      status_update_callback = self._PrintStatusUpdate
    else:
      status_update_callback = None

    self._front_end.ProcessSource(
        filter_file=self._filter_file,
        hasher_names_string=self._hasher_names_string,
        parser_filter_string=self._parser_filter_string,
        single_process_mode=self._single_process_mode,
        status_update_callback=status_update_callback,
        storage_serializer_format=self._storage_serializer_format,
        timezone=self._timezone)

    logging.info(u'Processing completed.')


def Main():
  """The main function."""
  multiprocessing.freeze_support()

  tool = Log2TimelineTool()

  if not tool.ParseArguments():
    return False

  # TODO: fix this. An explanation why this is needed is missing.
  # u_argv = [x.decode(front_end.preferred_encoding) for x in sys.argv]
  # sys.argv = u_argv

  have_list_option = False
  if tool.list_parsers_and_plugins:
    tool.ListPluginInformation()
    have_list_option = True

  if tool.list_timezones:
    tool.ListTimeZones()
    have_list_option = True

  if have_list_option:
    return True

  try:
    tool.ProcessSource()

  except (KeyboardInterrupt, errors.UserAbort):
    logging.warning(u'Aborted by user.')
    return False

  except errors.SourceScannerError as exception:
    logging.warning((
        u'Unable to scan for a supported filesystem with error: {0:s}\n'
        u'Most likely the image format is not supported by the '
        u'tool.').format(exception))
    return False

  return True


if __name__ == '__main__':
  if not Main():
    sys.exit(1)
  else:
    sys.exit(0)